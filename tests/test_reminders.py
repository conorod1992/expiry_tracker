"""Tests for the optional public-service Reminders adapter."""

from datetime import date
from types import SimpleNamespace

import pytest

from custom_components.expiry_tracker.manager import ExpiryTrackerManager
from custom_components.expiry_tracker.reminders import ReminderBackend, reminders_available

from .conftest import MemoryStorage, item_data


class Services:
    def __init__(self, available=True):
        self.available = available

    def has_service(self, domain, service):
        return self.available and domain == "reminders" and service in {"create", "list", "update", "delete"}


def test_capability_uses_only_public_services():
    assert reminders_available(SimpleNamespace(services=Services()))
    assert not reminders_available(SimpleNamespace(services=Services(False)))


@pytest.fixture
async def backend(monkeypatch):
    manager = ExpiryTrackerManager(MemoryStorage(), lambda: None)
    await manager.async_load()
    monkeypatch.setattr("custom_components.expiry_tracker.reminders.local_today", lambda: date(2026, 8, 24))
    return ReminderBackend(SimpleNamespace(services=Services()), manager), manager


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


async def test_lifecycle_acknowledges_only_expiry_tracker_item(backend):
    adapter, manager = backend
    item = await manager.async_create_item(item_data())
    await adapter.async_lifecycle(SimpleNamespace(data={"source": "other", "action": "acknowledged", "source_id": item.id}))
    assert not manager.get_item(item.id).acknowledged
    await adapter.async_lifecycle(SimpleNamespace(data={"source": "expiry_tracker", "action": "acknowledged", "source_id": item.id}))
    assert manager.get_item(item.id).acknowledged


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
