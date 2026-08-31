from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest
import voluptuous as vol
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.expiry_tracker.calculations import calculate_state
from custom_components.expiry_tracker.const import (
    CONF_DEFAULT_URGENT_DAYS,
    CONF_DEFAULT_WARNING_THRESHOLDS,
    DOMAIN,
)
from custom_components.expiry_tracker.manager import ExpiryTrackerManager
from custom_components.expiry_tracker.models import ExpiryItem, ItemValidationError
from custom_components.expiry_tracker.reminders import ReminderBackend
from custom_components.expiry_tracker.services import async_register_services

from .conftest import MemoryStorage, item_data


def test_date_fields_reject_datetime_subclasses():
    with pytest.raises(ItemValidationError, match="expiry_date must be an ISO date"):
        ExpiryItem.create(
            item_data(expiry_date=datetime(2027, 8, 19, 12, 0, tzinfo=UTC))
        )


def test_large_offsets_clamp_at_date_minimum():
    item = ExpiryItem.create(
        item_data(
            expiry_date="0001-01-02",
            actionable_offset_value=36500,
            warning_thresholds=[36500],
            urgent_days_before=36500,
        )
    )
    state = calculate_state(item, date.min)
    assert state.actionable_date == date.min
    assert state.warning_date == date.min
    assert state.urgent_date == date.min


async def test_future_attention_stage_cannot_be_acknowledged():
    manager = ExpiryTrackerManager(
        MemoryStorage(),
        lambda: None,
        lambda _value=None: date(2026, 8, 31),
    )
    await manager.async_load()
    item = await manager.async_create_item(
        item_data(expiry_date="2027-08-19", actionable_mode="immediate")
    )

    with pytest.raises(ValueError, match="only the active attention stage"):
        await manager.async_acknowledge(item.id, stage="expiry")

    current = await manager.async_acknowledge(item.id, stage="actionable")
    assert current.acknowledged_stage == "actionable"


async def test_search_can_explicitly_include_closed_items(manager):
    item = await manager.async_create_item(item_data())
    await manager.async_close(item.id, "Archived")

    assert manager.search("passport") == []
    assert [row.id for row in manager.search("passport", include_closed=True)] == [item.id]


async def test_services_apply_configured_defaults_and_have_fixed_ack_actions(hass):
    manager = ExpiryTrackerManager(
        MemoryStorage(),
        lambda: None,
        lambda _value=None: date(2026, 8, 31),
    )
    await manager.async_load()
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            CONF_DEFAULT_WARNING_THRESHOLDS: [60, 14],
            CONF_DEFAULT_URGENT_DAYS: 5,
        },
    )
    entry.runtime_data = manager
    entry.add_to_hass(hass)
    await async_register_services(hass)

    created = await hass.services.async_call(
        DOMAIN,
        "create_item",
        {
            "name": "Passport",
            "expiry_date": "2027-08-19",
            "actionable_mode": "immediate",
        },
        blocking=True,
        return_response=True,
    )
    item_id = created["item"]["id"]
    assert created["item"]["warning_thresholds"] == [60, 14]
    assert created["item"]["urgent_days_before"] == 5

    acknowledged = await hass.services.async_call(
        DOMAIN,
        "acknowledge_item",
        {"item_id": item_id},
        blocking=True,
        return_response=True,
    )
    assert acknowledged["item"]["acknowledged"] is True

    reset = await hass.services.async_call(
        DOMAIN,
        "reset_acknowledgement",
        {"item_id": item_id},
        blocking=True,
        return_response=True,
    )
    assert reset["item"]["acknowledged"] is False

    service_map = hass.services.async_services()[DOMAIN]
    with pytest.raises(vol.Invalid):
        service_map["reset_acknowledgement"].schema(
            {"item_id": item_id, "acknowledged": True}
        )


def test_reminders_milestones_tolerate_early_dates(monkeypatch):
    manager = ExpiryTrackerManager(MemoryStorage(), lambda: None)
    item = ExpiryItem.create(
        item_data(
            expiry_date="0001-01-02",
            actionable_offset_value=36500,
            warning_thresholds=[36500],
            urgent_days_before=36500,
        )
    )
    monkeypatch.setattr(
        "custom_components.expiry_tracker.reminders.local_today", lambda: date.min
    )
    backend = ReminderBackend(SimpleNamespace(), manager, "owner")

    milestones = backend._milestones(item)
    assert milestones["warning_36500"]["due"].startswith("0001-01-01")
