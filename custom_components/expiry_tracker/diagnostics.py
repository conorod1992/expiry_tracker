"""Privacy-safe aggregate diagnostics."""

from typing import Any

from homeassistant.components.diagnostics import REDACTED
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    BUILT_IN_CATEGORIES,
    CONF_NOTIFICATION_SERVICE,
    CONF_NOTIFICATION_TARGET,
    STORAGE_VERSION,
    VERSION,
)
from .manager import ExpiryTrackerManager


def _diagnostic_options(options: dict[str, Any]) -> dict[str, Any]:
    """Return collection options without exposing notification identifiers."""
    result = dict(options)
    for key in (CONF_NOTIFICATION_SERVICE, CONF_NOTIFICATION_TARGET):
        if key in result:
            result[key] = REDACTED
    return result


def _diagnostic_counts(manager: ExpiryTrackerManager) -> dict[str, Any]:
    """Return aggregate counts without exposing user-defined category names."""
    counts = manager.diagnostics_counts()
    category_counts = counts.pop("category_counts", {})
    built_in = set(BUILT_IN_CATEGORIES)
    custom = {
        category: count for category, count in category_counts.items() if category not in built_in
    }
    counts["category_counts"] = {
        category: category_counts[category]
        for category in BUILT_IN_CATEGORIES
        if category_counts.get(category)
    }
    counts["custom_category_count"] = len(custom)
    counts["custom_category_item_count"] = sum(custom.values())
    return counts


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry[ExpiryTrackerManager]
) -> dict[str, Any]:
    return {
        "integration_version": VERSION,
        "storage_schema_version": STORAGE_VERSION,
        "options": _diagnostic_options(dict(entry.options)),
        **_diagnostic_counts(entry.runtime_data),
    }
