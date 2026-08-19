"""Versioned, fail-safe Home Assistant storage."""

from __future__ import annotations

from typing import Any, cast

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_MINOR_VERSION, STORAGE_VERSION


async def _migrate(old_major: int, old_minor: int, old_data: dict[str, Any]) -> dict[str, Any]:
    """Migrate the public storage envelope without discarding records."""
    if old_major == 1:
        records = old_data.get("items")
        if not isinstance(records, list):
            raise ValueError("Expiry Tracker v1 storage is malformed")
        for row in records:
            if isinstance(row, dict):
                row.setdefault("history", [])
                row.setdefault("last_notifications", {})
        return {"schema_version": 2, "items": records}
    raise ValueError(f"Unsupported Expiry Tracker storage version {old_major}.{old_minor}")


class _ExpiryStore(Store[dict[str, Any]]):
    """Store subclass using Home Assistant's migration hook."""

    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int, old_data: dict[str, Any]
    ) -> dict[str, Any]:
        return await _migrate(old_major_version, old_minor_version, old_data)


class ExpiryTrackerStorage:
    def __init__(self, hass: HomeAssistant) -> None:
        self._store = _ExpiryStore(
            hass,
            STORAGE_VERSION,
            STORAGE_KEY,
            minor_version=STORAGE_MINOR_VERSION,
        )

    async def async_load(self) -> list[dict[str, Any]]:
        data = await self._store.async_load()
        if data is None:
            return []
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            raise ValueError("Expiry Tracker storage has an invalid top-level structure")
        if not all(isinstance(row, dict) for row in data["items"]):
            raise ValueError("Expiry Tracker storage contains a non-object record")
        return cast(list[dict[str, Any]], data["items"])

    async def async_save(self, records: list[dict[str, Any]]) -> None:
        await self._store.async_save(
            {"schema_version": STORAGE_VERSION, "items": sorted(records, key=lambda row: row["id"])}
        )
