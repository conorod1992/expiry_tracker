"""Tests for automatic recovery of the optional Reminders backend."""

from types import SimpleNamespace

from custom_components.expiry_tracker.manager import ExpiryTrackerManager
from custom_components.expiry_tracker.reminder_recovery import async_recover_reminders
from custom_components.expiry_tracker.reminders import ReminderBackend

from .conftest import MemoryStorage


async def _backend():
    manager = ExpiryTrackerManager(MemoryStorage(), lambda: None)
    await manager.async_load()
    hass = SimpleNamespace(data={})
    backend = ReminderBackend(hass, manager, "owner-user")
    hass.data["expiry_tracker_reminders_backend"] = backend
    hass.data["expiry_tracker_reminders_active"] = False
    return hass, backend, manager


async def test_successful_recovery_reactivates_backend_and_listener():
    hass, backend, manager = await _backend()
    calls = 0

    async def reconcile_all():
        nonlocal calls
        calls += 1
        return True

    backend.async_reconcile_all = reconcile_all  # type: ignore[method-assign]

    assert await async_recover_reminders(hass)
    assert calls == 1
    assert hass.data["expiry_tracker_reminders_active"] is True
    assert manager._change_listener == backend.async_changed


async def test_failed_recovery_keeps_native_fallback_and_can_retry():
    hass, backend, manager = await _backend()
    outcomes = iter((False, True))

    async def reconcile_all():
        return next(outcomes)

    backend.async_reconcile_all = reconcile_all  # type: ignore[method-assign]

    assert not await async_recover_reminders(hass)
    assert hass.data["expiry_tracker_reminders_active"] is False
    assert manager._change_listener is None

    assert await async_recover_reminders(hass)
    assert hass.data["expiry_tracker_reminders_active"] is True
    assert manager._change_listener == backend.async_changed


async def test_active_backend_is_not_reconciled_repeatedly():
    hass, backend, _manager = await _backend()
    hass.data["expiry_tracker_reminders_active"] = True
    calls = 0

    async def reconcile_all():
        nonlocal calls
        calls += 1
        return True

    backend.async_reconcile_all = reconcile_all  # type: ignore[method-assign]

    assert await async_recover_reminders(hass)
    assert calls == 0
