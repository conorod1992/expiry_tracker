from datetime import date
from types import SimpleNamespace

import pytest

from custom_components.expiry_tracker.manager import ExpiryTrackerManager
from custom_components.expiry_tracker.models import ExpiryItem, ItemValidationError
from custom_components.expiry_tracker.reminders import ReminderBackend

from .conftest import MemoryStorage, item_data


class Services:
    def has_service(self, domain, service):
        return domain == "reminders" and service in {
            "create",
            "list",
            "update",
            "delete",
            "external_action",
        }

    async def async_call(self, domain, service, data, **kwargs):
        self.last_call = (domain, service, data, kwargs)


class Bus:
    def async_fire(self, event_type, data):
        self.last_event = (event_type, data)


def test_action_type_defaults_and_custom_validation():
    default = ExpiryItem.create(item_data())
    assert default.action_type == "renew"
    assert default.custom_action_label is None

    custom = ExpiryItem.create(item_data(action_type="custom", custom_action_label="serviced"))
    assert custom.action_type == "custom"
    assert custom.custom_action_label == "serviced"

    with pytest.raises(ItemValidationError, match="custom_action_label is required"):
        ExpiryItem.create(item_data(action_type="custom"))
    with pytest.raises(ItemValidationError, match="action_type must be"):
        ExpiryItem.create(item_data(action_type="archive"))


async def test_workflow_edit_resets_acknowledgement_and_notification_history():
    manager = ExpiryTrackerManager(
        MemoryStorage(),
        lambda: None,
        local_date=lambda value=None: date(2026, 9, 3),
    )
    await manager.async_load()
    item = await manager.async_create_item(
        item_data(expiry_date="2026-10-03", actionable_mode="immediate")
    )
    item = await manager.async_acknowledge(item.id)
    await manager.async_record_notification(item.id, "actionable", "2026-09-03T08:00:00Z")

    updated = await manager.async_update_item(item.id, {"expiry_date": "2027-10-03"})

    assert not updated.acknowledged
    assert updated.acknowledged_stage is None
    assert updated.acknowledged_at is None
    assert updated.last_notifications == {}


async def test_notification_rule_edit_only_resets_notification_history():
    manager = ExpiryTrackerManager(
        MemoryStorage(),
        lambda: None,
        local_date=lambda value=None: date(2026, 9, 3),
    )
    await manager.async_load()
    item = await manager.async_create_item(
        item_data(expiry_date="2026-10-03", actionable_mode="immediate")
    )
    item = await manager.async_acknowledge(item.id)
    await manager.async_record_notification(item.id, "actionable", "2026-09-03T08:00:00Z")

    updated = await manager.async_update_item(item.id, {"warning_thresholds": [60, 30, 7]})

    assert updated.acknowledged
    assert updated.acknowledged_stage == item.acknowledged_stage
    assert updated.acknowledged_at == item.acknowledged_at
    assert updated.last_notifications == {}


async def test_metadata_edit_preserves_workflow_state():
    manager = ExpiryTrackerManager(
        MemoryStorage(),
        lambda: None,
        local_date=lambda value=None: date(2026, 9, 3),
    )
    await manager.async_load()
    item = await manager.async_create_item(
        item_data(expiry_date="2026-10-03", actionable_mode="immediate")
    )
    item = await manager.async_acknowledge(item.id)
    await manager.async_record_notification(item.id, "actionable", "2026-09-03T08:00:00Z")
    before = manager.get_item(item.id)

    updated = await manager.async_update_item(item.id, {"notes": "Updated paperwork notes"})

    assert updated.acknowledged == before.acknowledged
    assert updated.acknowledged_stage == before.acknowledged_stage
    assert updated.acknowledged_at == before.acknowledged_at
    assert updated.last_notifications == before.last_notifications


async def test_reminders_use_configured_completion_wording(monkeypatch):
    manager = ExpiryTrackerManager(MemoryStorage(), lambda: None)
    await manager.async_load()
    monkeypatch.setattr(
        "custom_components.expiry_tracker.reminders.local_today", lambda: date(2026, 8, 24)
    )
    adapter = ReminderBackend(
        SimpleNamespace(services=Services(), bus=Bus(), data={}), manager, "owner-user"
    )
    item = await manager.async_create_item(
        item_data(actionable_mode="immediate", action_type="review")
    )
    assert adapter._milestones(item)["actionable"]["external_actions"] == [
        {"id": "renewed", "label": "Reviewed"}
    ]


async def test_cancel_completion_closes_item(monkeypatch):
    manager = ExpiryTrackerManager(MemoryStorage(), lambda: None)
    await manager.async_load()
    monkeypatch.setattr(
        "custom_components.expiry_tracker.reminders.local_today", lambda: date(2026, 8, 24)
    )
    hass = SimpleNamespace(services=Services(), bus=Bus(), data={})
    adapter = ReminderBackend(hass, manager, "owner-user")
    hass.data["expiry_tracker_reminders_active"] = True
    item = await manager.async_create_item(
        item_data(actionable_mode="immediate", action_type="cancel")
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
    closed = manager.get_item(item.id)
    assert closed.closed
    assert closed.closed_reason == "Marked as cancelled"
