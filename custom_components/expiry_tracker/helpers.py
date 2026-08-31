"""Home Assistant adapter helpers."""

from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from .calculations import calculate_state
from .const import (
    CONF_DEFAULT_URGENT_DAYS,
    CONF_DEFAULT_WARNING_THRESHOLDS,
    DEFAULT_URGENT_DAYS,
    DEFAULT_WARNING_THRESHOLDS,
    DOMAIN,
)
from .manager import ExpiryTrackerManager
from .models import ExpiryItem


def get_entry(hass: HomeAssistant) -> ConfigEntry[ExpiryTrackerManager]:
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries or not hasattr(entries[0], "runtime_data"):
        raise HomeAssistantError("Expiry Tracker is not configured")
    return entries[0]


def get_manager(hass: HomeAssistant) -> ExpiryTrackerManager:
    return get_entry(hass).runtime_data


def creation_payload(hass: HomeAssistant, data: Mapping[str, Any]) -> dict[str, Any]:
    """Apply collection-wide create defaults only when callers omit them."""
    options = get_entry(hass).options
    result = dict(data)
    result.setdefault(
        "warning_thresholds",
        options.get(CONF_DEFAULT_WARNING_THRESHOLDS, DEFAULT_WARNING_THRESHOLDS),
    )
    result.setdefault(
        "urgent_days_before",
        options.get(CONF_DEFAULT_URGENT_DAYS, DEFAULT_URGENT_DAYS),
    )
    return result


def local_today() -> date:
    return dt_util.now().date()


def local_date(value: datetime | None = None) -> date:
    """Return a date in Home Assistant's configured local timezone."""
    return dt_util.as_local(value).date() if value is not None else local_today()


def parse_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as err:
        raise HomeAssistantError(f"{field} must be an ISO date (YYYY-MM-DD)") from err


def decorate(item: ExpiryItem, today: date | None = None) -> dict[str, Any]:
    return {**item.to_dict(), **calculate_state(item, today or local_today()).to_dict()}
