from datetime import UTC, date, datetime

from custom_components.expiry_tracker.calendar import ExpiryTrackerCalendar
from custom_components.expiry_tracker.sensor import (
    ExpiryItemSensor,
    NextExpirySensor,
    StatusCountSensor,
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
