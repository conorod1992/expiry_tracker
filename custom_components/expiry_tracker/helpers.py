"""Home Assistant adapter helpers."""

from datetime import date
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from .calculations import calculate_state
from .const import DOMAIN
from .manager import ExpiryTrackerManager
from .models import ExpiryItem


def get_entry(hass: HomeAssistant) -> ConfigEntry[ExpiryTrackerManager]:
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries or not hasattr(entries[0], "runtime_data"):
        raise HomeAssistantError("Expiry Tracker is not configured")
    return entries[0]


def get_manager(hass: HomeAssistant) -> ExpiryTrackerManager:
    return get_entry(hass).runtime_data


def local_today() -> date:
    return dt_util.now().date()


def parse_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as err:
        raise HomeAssistantError(f"{field} must be an ISO date (YYYY-MM-DD)") from err


def decorate(item: ExpiryItem, today: date | None = None) -> dict[str, Any]:
    return {**item.to_dict(), **calculate_state(item, today or local_today()).to_dict()}
