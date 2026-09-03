"""Automatic recovery for a temporarily unavailable Reminders backend."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .reminders import ReminderBackend

_ACTIVE_DATA_KEY = "expiry_tracker_reminders_active"
_BACKEND_DATA_KEY = "expiry_tracker_reminders_backend"
_RECOVERY_INTERVAL = timedelta(minutes=5)


async def async_recover_reminders(hass: HomeAssistant) -> bool:
    """Re-enable an existing Reminders backend after a transient failure."""
    if hass.data.get(_ACTIVE_DATA_KEY):
        return True
    backend = hass.data.get(_BACKEND_DATA_KEY)
    if not isinstance(backend, ReminderBackend):
        return False
    if not await backend.async_reconcile_all():
        return False
    backend.manager.set_change_listener(backend.async_changed)
    hass.data[_ACTIVE_DATA_KEY] = True
    return True


def async_setup_reminder_recovery(hass: HomeAssistant) -> CALLBACK_TYPE:
    """Periodically retry only a previously configured but inactive backend."""

    async def scheduled(_now: datetime) -> None:
        await async_recover_reminders(hass)

    return async_track_time_interval(hass, scheduled, _RECOVERY_INTERVAL)
