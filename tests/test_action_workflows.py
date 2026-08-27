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


async def test_reminders_use_configured_completion_wording(monkeypatch):
    manager = ExpiryTrackerManager(MemoryStorage(), lambda: None)
    await manager.async_load()
    monkeypatch.setattr(
        "custom_components.expiry_tracker.reminders.local_today", lambda: date(2026, 8, 24)
    )
    adapter = ReminderBackend(SimpleNamespace(services=Services(), bus=Bus()), manager)
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
    adapter = ReminderBackend(SimpleNamespace(services=Services(), bus=Bus()), manager)
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
