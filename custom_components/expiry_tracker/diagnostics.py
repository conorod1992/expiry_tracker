"""Privacy-safe aggregate diagnostics."""

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import STORAGE_VERSION, VERSION
from .manager import ExpiryTrackerManager


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry[ExpiryTrackerManager]
) -> dict[str, Any]:
    return {
        "integration_version": VERSION,
        "storage_schema_version": STORAGE_VERSION,
        "options": dict(entry.options),
        **entry.runtime_data.diagnostics_counts(),
    }
