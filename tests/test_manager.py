from datetime import date

import pytest

from custom_components.expiry_tracker.models import ItemNotFoundError, ItemValidationError

from .conftest import item_data


async def test_crud_stable_id_and_query_filters(manager):
    first = await manager.async_create_item(item_data(important=True, actionable_offset_value=365))
    disabled = await manager.async_create_item(
        item_data(
            name="Insurance",
            expiry_date="2026-09-01",
            category="Insurance",
            enabled=False,
            actionable_mode="immediate",
        )
    )
    renamed = await manager.async_update_item(first.id, {"name": "Irish passport"})
    assert renamed.id == first.id
    assert manager.search("passport")[0].id == first.id
    rows = manager.query(date(2026, 8, 19), actionable_only=True, important_only=True)
    assert [row[0].id for row in rows] == [first.id]
    assert disabled.id not in {row[0].id for row in manager.query(date(2026, 8, 19))}
    await manager.async_delete_item(first.id)
    with pytest.raises(ItemNotFoundError):
        manager.get_item(first.id)


async def test_acknowledge_history_and_reset(manager):
    item = await manager.async_create_item(
        item_data(actionable_mode="immediate", require_acknowledgement=True)
    )
    acknowledged = await manager.async_acknowledge(item.id)
    assert acknowledged.acknowledged and acknowledged.acknowledged_at
    assert acknowledged.acknowledged_stage == "actionable"
    assert acknowledged.history[-1]["type"] == "acknowledged"
    reset = await manager.async_acknowledge(item.id, False)
    assert not reset.acknowledged
    assert reset.history[-1]["type"] == "acknowledgement_reset"


async def test_renewal_resets_state_and_retains_history(manager):
    item = await manager.async_create_item(
        item_data(actionable_mode="immediate", recurrence_months=12)
    )
    await manager.async_acknowledge(item.id)
    await manager.async_record_notification(item.id, "urgent", "2026-01-01T00:00:00Z")
    renewed = await manager.async_renew(item.id)
    assert renewed.expiry_date == date(2028, 8, 19)
    assert not renewed.acknowledged
    assert renewed.acknowledged_stage is None
    assert renewed.last_notifications == {}
    assert renewed.history[-1]["previous_expiry_date"] == "2027-08-19"


async def test_manual_renewal_required_without_recurrence(manager):
    item = await manager.async_create_item(item_data())
    with pytest.raises(ValueError, match="required"):
        await manager.async_renew(item.id)
    with pytest.raises(ValueError, match="after"):
        await manager.async_renew(item.id, date(2027, 1, 1))


async def test_immutable_and_invalid_fields(manager):
    item = await manager.async_create_item(item_data())
    with pytest.raises(ItemValidationError):
        await manager.async_update_item(item.id, {"id": "changed"})
    with pytest.raises(ItemValidationError):
        await manager.async_update_item(
            item.id, {"actionable_mode": "date", "actionable_from": None}
        )


async def test_atomic_rollback_on_save_failure():
    from custom_components.expiry_tracker.manager import ExpiryTrackerManager

    from .conftest import MemoryStorage

    storage = MemoryStorage()
    manager = ExpiryTrackerManager(storage, lambda: None)
    await manager.async_load()
    item = await manager.async_create_item(item_data())

    async def fail(records):
        raise RuntimeError("disk")

    storage.async_save = fail
    with pytest.raises(RuntimeError):
        await manager.async_delete_item(item.id)
    assert manager.get_item(item.id) == item


async def test_legacy_acknowledgement_migrates_to_active_stage():
    from custom_components.expiry_tracker.manager import ExpiryTrackerManager

    from .conftest import MemoryStorage

    record = {
        **item_data(actionable_mode="immediate", acknowledged=True),
        "id": "a6bdbf74-0608-4be2-a127-f3b1b969bd61",
        "acknowledged_at": "2026-08-20T10:00:00Z",
    }
    storage = MemoryStorage([record])
    loaded = ExpiryTrackerManager(storage, lambda: None)
    await loaded.async_load()
    assert loaded.list_items()[0].acknowledged_stage == "actionable"
    assert storage.records[0]["acknowledged_stage"] == "actionable"
