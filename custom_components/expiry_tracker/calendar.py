"""Collection calendar projection for expiry dates."""

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import SIGNAL_UPDATED
from .helpers import local_today
from .manager import ExpiryTrackerManager
from .models import ExpiryItem


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[ExpiryTrackerManager],
    async_add_entities: AddEntitiesCallback,
) -> None:
    entity = ExpiryTrackerCalendar(entry.runtime_data)
    async_add_entities([entity])

    @callback
    def update() -> None:
        if entity.hass is not None:
            entity.async_write_ha_state()

    entry.async_on_unload(async_dispatcher_connect(hass, SIGNAL_UPDATED, update))


class ExpiryTrackerCalendar(CalendarEntity):
    _attr_has_entity_name = True
    _attr_name = "Expiries"
    _attr_unique_id = "expiry_tracker_calendar"
    _attr_icon = "mdi:calendar-alert"

    def __init__(self, manager: ExpiryTrackerManager) -> None:
        self._manager = manager

    @staticmethod
    def _event(item: ExpiryItem) -> CalendarEvent:
        return CalendarEvent(
            start=item.expiry_date,
            end=item.expiry_date + timedelta(days=1),
            summary=f"{item.name} expires",
            description=f"Expiry Tracker category: {item.category}",
            uid=f"expiry:{item.id}:{item.expiry_date.isoformat()}",
            recurrence_id=item.expiry_date.isoformat(),
        )

    @property
    def event(self) -> CalendarEvent | None:
        rows = [
            item
            for item in self._manager.list_items()
            if item.enabled and not item.closed and item.expiry_date >= local_today()
        ]
        return self._event(min(rows, key=lambda item: item.expiry_date)) if rows else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        start, end = start_date.date(), end_date.date()
        return [
            self._event(item)
            for item in self._manager.list_items()
            if item.enabled and not item.closed and start <= item.expiry_date < end
        ]
