"""Automatic recovery for a temporarily unavailable Reminders backend."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_USE_REMINDERS
from .helpers import get_manager
from .reminders import (
    ReminderBackend,
    async_cleanup_reminders,
    async_setup_reminders,
)

_ACTIVE_DATA_KEY = "expiry_tracker_reminders_active"
_BACKEND_DATA_KEY = "expiry_tracker_reminders_backend"
_RECOVERY_INTERVAL = timedelta(minutes=5)


async def async_recover_reminders(hass: HomeAssistant, entry: Any) -> bool:
    """Recover or clean up Reminders according to the current configuration."""
    use_reminders = entry.options.get(CONF_USE_REMINDERS, False)
    backend = hass.data.get(_BACKEND_DATA_KEY)

    if not use_reminders:
        if not isinstance(backend, ReminderBackend):
            hass.data[_ACTIVE_DATA_KEY] = False
            return True
        return await async_cleanup_reminders(hass)

    if hass.data.get(_ACTIVE_DATA_KEY):
        return True

    if not isinstance(backend, ReminderBackend):
        unsubscribe = await async_setup_reminders(hass, entry, get_manager(hass))
        if unsubscribe is not None:
            entry.async_on_unload(unsubscribe)
        return bool(hass.data.get(_ACTIVE_DATA_KEY))

    if not await backend.async_reconcile_all():
        return False
    backend.manager.set_change_listener(backend.async_changed)
    hass.data[_ACTIVE_DATA_KEY] = True
    return True


def async_setup_reminder_recovery(hass: HomeAssistant, entry: Any) -> CALLBACK_TYPE:
    """Periodically restore or clean up Reminders according to configuration."""

    async def scheduled(_now: datetime) -> None:
        await async_recover_reminders(hass, entry)

    return async_track_time_interval(hass, scheduled, _RECOVERY_INTERVAL)
