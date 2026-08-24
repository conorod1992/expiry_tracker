"""Tests for the optional public-service Reminders adapter."""

from datetime import date
from types import SimpleNamespace

import pytest

from custom_components.expiry_tracker.const import CONF_USE_REMINDERS
from custom_components.expiry_tracker.manager import ExpiryTrackerManager
from custom_components.expiry_tracker.reminders import (
    ReminderBackend,
    async_setup_reminders,
    reminders_available,
)

from .conftest import MemoryStorage, item_data


class Services:
    def __init__(self, available=True, missing=()):
        self.available = available
        self.missing = set(missing)

    def has_service(self, domain, service):
        return (
            self.available
            and domain == "reminders"
            and service in {"create", "list", "update", "delete", "external_action"}
            and service not in self.missing
        )

    async def async_call(self, domain, service, data, **kwargs):
        self.last_call = (domain, service, data, kwargs)


class Bus:
    def async_fire(self, event_type, data):
        self.last_event = (event_type, data)


def test_capability_requires_all_public_services():
    assert reminders_available(SimpleNamespace(services=Services()))
    assert not reminders_available(SimpleNamespace(services=Services(False)))
    assert not reminders_available(SimpleNamespace(services=Services(missing={"external_action"})))


async def test_missing_external_action_keeps_native_notifications_active():
    manager = ExpiryTrackerManager(MemoryStorage(), lambda: None)
    await manager.async_load()
    hass = SimpleNamespace(services=Services(missing={"external_action"}), data={})
    entry = SimpleNamespace(options={CONF_USE_REMINDERS: True})
    assert await async_setup_reminders(hass, entry, manager) is None
    assert hass.data["expiry_tracker_reminders_active"] is False


@pytest.fixture
async def backend(monkeypatch):
    manager = ExpiryTrackerManager(MemoryStorage(), lambda: None)
    await manager.async_load()
    monkeypatch.setattr(
        "custom_components.expiry_tracker.reminders.local_today", lambda: date(2026, 8, 24)
    )
    return ReminderBackend(SimpleNamespace(services=Services(), bus=Bus()), manager), manager


async def test_milestones_have_stable_source_identity_and_do_not_replay_past_warnings(backend):
    adapter, manager = backend
    item = await manager.async_create_item(
        item_data(expiry_date="2026-09-10", warning_thresholds=[90, 7], actionable_offset_value=5)
    )
    milestones = adapter._milestones(item)
    assert "warning_90" not in milestones
    assert milestones["warning_7"]["source"] == "expiry_tracker"
    assert milestones["warning_7"]["source_id"] == item.id
    assert milestones["warning_7"]["source_event"] == "warning_7"
    assert milestones["warning_7"]["acknowledgement_policy"] == "not_required"
    assert milestones["warning_7"]["allow_manual_completion"] is False
    assert milestones["warning_7"]["external_actions"] == []
    assert milestones["actionable"]["external_actions"] == [{"id": "renewed", "label": "Renewed"}]
    assert milestones["actionable"]["allow_manual_completion"] is False


async def test_expiry_day_uses_expiry_attention_stage(backend, monkeypatch):
    adapter, manager = backend
    monkeypatch.setattr(
        "custom_components.expiry_tracker.reminders.local_today", lambda: date(2026, 9, 10)
    )
    item = await manager.async_create_item(item_data(expiry_date="2026-09-10"))
    milestones = adapter._milestones(item)
    assert set(milestones) == {"expiry"}
    assert milestones["expiry"]["acknowledgement_policy"] == "required"


async def test_current_attention_stage_is_reconciled_without_replaying_warnings(backend):
    adapter, manager = backend
    item = await manager.async_create_item(
        item_data(expiry_date="2026-09-10", actionable_mode="immediate", warning_thresholds=[90])
    )
    milestones = adapter._milestones(item)
    assert "warning_90" not in milestones
    assert milestones["actionable"]["due"] == "2026-08-24 09:00:00"


async def test_dismiss_lifecycle_acknowledges_only_matching_stage(backend):
    adapter, manager = backend
    item = await manager.async_create_item(item_data(actionable_mode="immediate"))
    await adapter.async_lifecycle(
        SimpleNamespace(
            data={
                "source": "other",
                "action": "dismissed",
                "source_id": item.id,
                "source_event": "actionable",
            }
        )
    )
    assert not manager.get_item(item.id).acknowledged
    await adapter.async_lifecycle(
        SimpleNamespace(
            data={
                "source": "expiry_tracker",
                "action": "dismissed",
                "source_id": item.id,
                "source_event": "warning_7",
            }
        )
    )
    assert not manager.get_item(item.id).acknowledged
    await adapter.async_lifecycle(
        SimpleNamespace(
            data={
                "source": "expiry_tracker",
                "action": "dismissed",
                "source_id": item.id,
                "source_event": "actionable",
            }
        )
    )
    assert manager.get_item(item.id).acknowledged_stage == "actionable"


async def test_external_renewed_requests_confirmation_without_renewing(backend):
    adapter, manager = backend
    item = await manager.async_create_item(
        item_data(actionable_mode="immediate", recurrence_months=12)
    )
    await adapter.async_lifecycle(
        SimpleNamespace(
            data={
                "source": "expiry_tracker",
                "action": "external_action_selected",
                "external_action_id": "renewed",
                "source_id": item.id,
                "source_event": "actionable",
            }
        )
    )
    assert manager.get_item(item.id).expiry_date == date(2027, 8, 19)
    assert adapter.hass.bus.last_event[0] == "expiry_tracker_renewal_requested"
    assert "?renew=" in adapter.hass.services.last_call[2]["message"]


async def test_generic_completion_cannot_renew(backend):
    adapter, manager = backend
    item = await manager.async_create_item(item_data(actionable_mode="immediate"))
    for action in ("manually_completed", "automatically_completed"):
        await adapter.async_lifecycle(
            SimpleNamespace(
                data={
                    "source": "expiry_tracker",
                    "action": action,
                    "source_id": item.id,
                    "source_event": "actionable",
                }
            )
        )
    unchanged = manager.get_item(item.id)
    assert unchanged.expiry_date == date(2027, 8, 19)
    assert not unchanged.acknowledged


async def test_reconciliation_does_not_create_duplicates_after_restart(backend):
    adapter, manager = backend
    item = await manager.async_create_item(item_data(expiry_date="2026-10-01"))
    remote: list[dict] = []
    created = 0

    async def call(service, data, *, response=False):
        nonlocal created
        if service == "list":
            return {"reminders": remote}
        if service == "create":
            created += 1
            remote.append({"id": str(created), **data})
        return None

    adapter._call = call  # type: ignore[method-assign]
    await adapter.async_reconcile(item)
    await adapter.async_reconcile(item)
    assert created == len(adapter._milestones(item))
