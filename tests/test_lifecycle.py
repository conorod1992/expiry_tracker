"""Regression tests for renewal and close lifecycle behaviour."""

from datetime import date

from custom_components.expiry_tracker.calculations import ExpiryStatus, calculate_state
from custom_components.expiry_tracker.manager import ExpiryTrackerManager

from .conftest import MemoryStorage, item_data


async def test_overdue_recurrence_advances_to_next_future_expiry():
    manager = ExpiryTrackerManager(
        MemoryStorage(), lambda: None, lambda _value=None: date(2026, 8, 27)
    )
    await manager.async_load()
    item = await manager.async_create_item(
        item_data(expiry_date="2024-08-19", recurrence_months=12)
    )

    renewed = await manager.async_renew(item.id)

    assert renewed.expiry_date == date(2027, 8, 19)
    assert renewed.history[-1] == {
        "type": "renewed",
        "at": renewed.updated_at,
        "previous_expiry_date": "2024-08-19",
        "new_expiry_date": "2027-08-19",
    }


async def test_close_and_reopen_preserve_item_and_history():
    manager = ExpiryTrackerManager(MemoryStorage(), lambda: None)
    await manager.async_load()
    item = await manager.async_create_item(item_data(actionable_mode="immediate"))

    closed = await manager.async_close(item.id, "No longer needed")

    assert closed.id == item.id
    assert closed.closed
    assert closed.closed_at
    assert closed.closed_reason == "No longer needed"
    assert closed.history[-1]["type"] == "closed"
    assert manager.query(date(2027, 8, 20)) == []
    assert manager.search("Passport") == []

    reopened = await manager.async_reopen(item.id)

    assert not reopened.closed
    assert reopened.closed_at is None
    assert reopened.closed_reason is None
    assert reopened.history[-1]["type"] == "reopened"
    assert manager.search("Passport")[0].id == item.id


def test_passive_expiry_never_requires_action_but_still_expires():
    from custom_components.expiry_tracker.models import ExpiryItem

    item = ExpiryItem.create(
        item_data(
            expiry_date="2026-08-20",
            requires_action=False,
            actionable_mode="immediate",
            urgent_days_before=30,
        )
    )

    before = calculate_state(item, date(2026, 8, 19))
    after = calculate_state(item, date(2026, 8, 21))

    assert before.status is ExpiryStatus.WARNING
    assert not before.actionable
    assert before.attention_stage is None
    assert not before.requires_attention
    assert after.status is ExpiryStatus.EXPIRED
    assert not after.requires_attention
    assert not after.renewal_outstanding


def test_required_expired_item_is_marked_renewal_outstanding():
    from custom_components.expiry_tracker.models import ExpiryItem

    item = ExpiryItem.create(item_data(expiry_date="2026-08-20"))
    state = calculate_state(item, date(2026, 8, 21))

    assert state.status is ExpiryStatus.EXPIRED
    assert state.requires_attention
    assert state.renewal_outstanding
