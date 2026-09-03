from datetime import UTC, datetime
from types import SimpleNamespace

from custom_components.expiry_tracker.calendar import ExpiryTrackerCalendar

from .conftest import item_data


async def test_calendar_range_events_are_chronological(manager):
    await manager.async_create_item(item_data(name="Alpha", expiry_date="2026-09-20"))
    await manager.async_create_item(item_data(name="Zulu", expiry_date="2026-09-05"))
    await manager.async_create_item(item_data(name="Bravo", expiry_date="2026-09-10"))

    calendar = ExpiryTrackerCalendar(manager)
    events = await calendar.async_get_events(
        SimpleNamespace(),
        datetime(2026, 9, 1, tzinfo=UTC),
        datetime(2026, 10, 1, tzinfo=UTC),
    )

    assert [event.start.isoformat() for event in events] == [
        "2026-09-05",
        "2026-09-10",
        "2026-09-20",
    ]
