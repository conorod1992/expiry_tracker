from typing import Any

import pytest

from custom_components.expiry_tracker.manager import ExpiryTrackerManager


class MemoryStorage:
    def __init__(self, records: list[dict[str, Any]] | None = None) -> None:
        self.records = list(records or [])
        self.save_count = 0

    async def async_load(self):
        return list(self.records)

    async def async_save(self, records):
        self.records = list(records)
        self.save_count += 1


@pytest.fixture
async def manager():
    value = ExpiryTrackerManager(MemoryStorage(), lambda: None)
    await value.async_load()
    return value


def item_data(**changes: Any) -> dict[str, Any]:
    return {
        "name": "Passport",
        "expiry_date": "2027-08-19",
        "category": "Identity/document",
        **changes,
    }
