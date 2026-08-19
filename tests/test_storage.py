import pytest

from custom_components.expiry_tracker.storage import _migrate


async def test_storage_v1_migration_preserves_records():
    record = {"id": "x", "name": "Passport"}
    result = await _migrate(1, 0, {"items": [record]})
    assert result["schema_version"] == 2
    assert result["items"][0]["name"] == "Passport"
    assert result["items"][0]["history"] == []


async def test_unknown_or_corrupt_migration_fails_safely():
    with pytest.raises(ValueError):
        await _migrate(1, 0, {"items": "bad"})
    with pytest.raises(ValueError):
        await _migrate(99, 0, {})
