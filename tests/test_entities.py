from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import Mock

from custom_components.expiry_tracker.calendar import ExpiryTrackerCalendar
from custom_components.expiry_tracker.const import DOMAIN
from custom_components.expiry_tracker.sensor import (
    ExpiryItemSensor,
    NextExpirySensor,
    StatusCountSensor,
    _remove_orphaned_item_registry_entries,
)

from .conftest import item_data


async def test_entity_identity_survives_rename(manager, freezer):
    freezer.move_to("2026-08-19 12:00:00+00:00")
    item = await manager.async_create_item(item_data(expose_entity=True))
    sensor = ExpiryItemSensor(manager, item.id)
    unique_id = sensor.unique_id
    await manager.async_update_item(item.id, {"name": "Renamed"})
    assert sensor.unique_id == unique_id == f"item_{item.id}"
    assert sensor.name == "Renamed"
    assert sensor.native_value == date(2027, 8, 19)


def test_registry_cleanup_removes_only_deleted_expiry_item_entities(monkeypatch):
    registry = SimpleNamespace(async_remove=Mock())
    entries = [
        SimpleNamespace(
            entity_id="sensor.deleted",
            domain="sensor",
            platform=DOMAIN,
            unique_id="item_deleted",
        ),
        SimpleNamespace(
            entity_id="sensor.hidden_but_live",
            domain="sensor",
            platform=DOMAIN,
            unique_id="item_live",
        ),
        SimpleNamespace(
            entity_id="sensor.aggregate",
            domain="sensor",
            platform=DOMAIN,
            unique_id="expiry_tracker_expired",
        ),
        SimpleNamespace(
            entity_id="sensor.other_platform",
            domain="sensor",
            platform="other",
            unique_id="item_deleted",
        ),
    ]
    monkeypatch.setattr(
        "custom_components.expiry_tracker.sensor.er.async_get", lambda _hass: registry
    )
    monkeypatch.setattr(
        "custom_components.expiry_tracker.sensor.er.async_entries_for_config_entry",
        lambda _registry, entry_id: entries if entry_id == "entry" else [],
    )

    _remove_orphaned_item_registry_entries(
        SimpleNamespace(), SimpleNamespace(entry_id="entry"), {"live"}
    )

    registry.async_remove.assert_called_once_with("sensor.deleted")


def test_registry_cleanup_preserves_hidden_item_until_source_is_deleted(monkeypatch):
    registry = SimpleNamespace(async_remove=Mock())
    entry_record = SimpleNamespace(
        entity_id="sensor.passport",
        domain="sensor",
        platform=DOMAIN,
        unique_id="item_passport",
    )
    monkeypatch.setattr(
        "custom_components.expiry_tracker.sensor.er.async_get", lambda _hass: registry
    )
    monkeypatch.setattr(
        "custom_components.expiry_tracker.sensor.er.async_entries_for_config_entry",
        lambda _registry, _entry_id: [entry_record],
    )
    entry = SimpleNamespace(entry_id="entry")

    _remove_orphaned_item_registry_entries(SimpleNamespace(), entry, {"passport"})
    registry.async_remove.assert_not_called()

    _remove_orphaned_item_registry_entries(SimpleNamespace(), entry, set())
    registry.async_remove.assert_called_once_with("sensor.passport")


async def test_aggregate_entities_are_bounded(manager, freezer):
    freezer.move_to("2026-08-19 12:00:00+00:00")
    await manager.async_create_item(item_data(actionable_mode="immediate"))
    next_sensor = NextExpirySensor(manager, actionable=True)
    assert next_sensor.native_value == date(2027, 8, 19)
    assert set(next_sensor.extra_state_attributes) == {
        "item_id",
        "name",
        "category",
        "days_until_expiry",
        "status",
        "requires_attention",
        "renewal_outstanding",
    }
    assert StatusCountSensor(manager, "actionable").native_value == 1


async def test_calendar_excludes_disabled_and_range_end(manager):
    enabled = await manager.async_create_item(item_data(expiry_date="2027-01-01"))
    await manager.async_create_item(
        item_data(name="Disabled", expiry_date="2027-01-01", enabled=False)
    )
    calendar = ExpiryTrackerCalendar(manager)
    rows = await calendar.async_get_events(
        None, datetime(2027, 1, 1, tzinfo=UTC), datetime(2027, 1, 2, tzinfo=UTC)
    )
    assert len(rows) == 1 and rows[0].uid.startswith(f"expiry:{enabled.id}")
    assert rows[0].all_day
