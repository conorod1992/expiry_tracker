"""Tests for automatic recovery of the optional Reminders backend."""

from types import SimpleNamespace

from custom_components.expiry_tracker.const import CONF_USE_REMINDERS
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
    entry = SimpleNamespace(options={CONF_USE_REMINDERS: True})
    return hass, entry, backend, manager


async def test_successful_recovery_reactivates_backend_and_listener():
    hass, entry, backend, manager = await _backend()
    calls = 0

    async def reconcile_all():
        nonlocal calls
        calls += 1
        return True

    backend.async_reconcile_all = reconcile_all  # type: ignore[method-assign]

    assert await async_recover_reminders(hass, entry)
    assert calls == 1
    assert hass.data["expiry_tracker_reminders_active"] is True
    assert manager._change_listener == backend.async_changed


async def test_failed_recovery_keeps_native_fallback_and_can_retry():
    hass, entry, backend, manager = await _backend()
    outcomes = iter((False, True))

    async def reconcile_all():
        return next(outcomes)

    backend.async_reconcile_all = reconcile_all  # type: ignore[method-assign]

    assert not await async_recover_reminders(hass, entry)
    assert hass.data["expiry_tracker_reminders_active"] is False
    assert manager._change_listener is None

    assert await async_recover_reminders(hass, entry)
    assert hass.data["expiry_tracker_reminders_active"] is True
    assert manager._change_listener == backend.async_changed


async def test_active_backend_is_not_reconciled_repeatedly():
    hass, entry, backend, _manager = await _backend()
    hass.data["expiry_tracker_reminders_active"] = True
    calls = 0

    async def reconcile_all():
        nonlocal calls
        calls += 1
        return True

    backend.async_reconcile_all = reconcile_all  # type: ignore[method-assign]

    assert await async_recover_reminders(hass, entry)
    assert calls == 0


async def test_missing_backend_retries_normal_setup(monkeypatch):
    manager = ExpiryTrackerManager(MemoryStorage(), lambda: None)
    await manager.async_load()
    hass = SimpleNamespace(data={})
    unload_callbacks = []
    entry = SimpleNamespace(
        options={CONF_USE_REMINDERS: True},
        async_on_unload=unload_callbacks.append,
    )
    unsubscribe = lambda: None
    calls = 0

    monkeypatch.setattr(
        "custom_components.expiry_tracker.reminder_recovery.get_manager", lambda _hass: manager
    )

    async def setup(_hass, _entry, _manager):
        nonlocal calls
        calls += 1
        hass.data["expiry_tracker_reminders_active"] = True
        return unsubscribe

    monkeypatch.setattr(
        "custom_components.expiry_tracker.reminder_recovery.async_setup_reminders", setup
    )

    assert await async_recover_reminders(hass, entry)
    assert calls == 1
    assert unload_callbacks == [unsubscribe]


async def test_disabled_backend_retries_cleanup_without_reactivating():
    hass, entry, backend, manager = await _backend()
    entry.options[CONF_USE_REMINDERS] = False
    hass.data["expiry_tracker_reminders_active"] = False
    manager.set_change_listener(backend.async_changed)
    outcomes = iter((False, True))

    async def remove_all():
        return next(outcomes)

    backend.async_remove_all = remove_all  # type: ignore[method-assign]

    assert not await async_recover_reminders(hass, entry)
    assert hass.data["expiry_tracker_reminders_active"] is False
    assert manager._change_listener is None
    assert hass.data["expiry_tracker_reminders_backend"] is backend

    assert await async_recover_reminders(hass, entry)
    assert hass.data["expiry_tracker_reminders_active"] is False
    assert "expiry_tracker_reminders_backend" not in hass.data
