"""Regression tests for Reminders duplicate reconciliation and cleanup."""

from datetime import date
from types import SimpleNamespace

import custom_components.expiry_tracker as expiry_tracker
from custom_components.expiry_tracker.manager import ExpiryTrackerManager
from custom_components.expiry_tracker.reminders import (
    ReminderBackend,
    async_cleanup_reminders,
)

from .conftest import MemoryStorage, item_data


class Services:
    def has_service(self, domain, service):
        return domain == "reminders" and service in {
            "create",
            "list",
            "update",
            "delete",
            "external_action",
        }


class Bus:
    def async_fire(self, event_type, data):
        return None


def hass_for():
    return SimpleNamespace(services=Services(), bus=Bus(), data={})


async def test_duplicate_reconciliation_keeps_selected_survivor(monkeypatch):
    manager = ExpiryTrackerManager(MemoryStorage(), lambda: None)
    await manager.async_load()
    monkeypatch.setattr(
        "custom_components.expiry_tracker.reminders.local_today", lambda: date(2026, 8, 24)
    )
    adapter = ReminderBackend(hass_for(), manager, "owner-user")
    item = await manager.async_create_item(
        item_data(expiry_date="2026-10-01", warning_thresholds=[7])
    )
    event, wanted = next(iter(adapter._milestones(item).items()))
    remote = [
        {"id": "20", **wanted},
        {"id": "10", **wanted},
        {"id": "30", **wanted},
    ]
    deleted: list[str] = []
    updated: list[str] = []

    async def call(service, data, *, response=False):
        if service == "list":
            return {"reminders": remote}
        if service == "delete":
            deleted.append(data["reminder_id"])
        if service == "update":
            updated.append(data["reminder_id"])
        return None

    adapter._call = call  # type: ignore[method-assign]

    assert await adapter.async_reconcile(item)
    assert event == remote[0]["source_event"]
    assert set(deleted) == {"20", "30"}
    assert "10" not in deleted
    assert updated == []


async def test_malformed_duplicate_does_not_block_expected_recreation(monkeypatch):
    manager = ExpiryTrackerManager(MemoryStorage(), lambda: None)
    await manager.async_load()
    monkeypatch.setattr(
        "custom_components.expiry_tracker.reminders.local_today", lambda: date(2026, 8, 24)
    )
    adapter = ReminderBackend(hass_for(), manager, "owner-user")
    item = await manager.async_create_item(
        item_data(expiry_date="2026-10-01", warning_thresholds=[7])
    )
    event, wanted = next(iter(adapter._milestones(item).items()))
    remote = [{**wanted}]
    created: list[dict] = []

    async def call(service, data, *, response=False):
        if service == "list":
            return {"reminders": remote}
        if service == "create":
            created.append(data)
        return None

    adapter._call = call  # type: ignore[method-assign]

    assert await adapter.async_reconcile(item)
    assert any(value["source_event"] == event for value in created)


async def test_cleanup_removes_all_source_owned_reminders(monkeypatch):
    manager = ExpiryTrackerManager(MemoryStorage(), lambda: None)
    await manager.async_load()
    hass = hass_for()
    adapter = ReminderBackend(hass, manager, "owner-user")
    manager.set_change_listener(adapter.async_changed)
    hass.data["expiry_tracker_reminders_backend"] = adapter
    hass.data["expiry_tracker_reminders_active"] = True
    remote = [
        {"id": "1", "source": "expiry_tracker"},
        {"id": "2", "source": "expiry_tracker"},
        {"id": "3", "source": "other"},
    ]
    deleted: list[str] = []

    async def call(service, data, *, response=False):
        if service == "list":
            return {"reminders": remote}
        if service == "delete":
            deleted.append(data["reminder_id"])
        return None

    adapter._call = call  # type: ignore[method-assign]

    assert await async_cleanup_reminders(hass)
    assert set(deleted) == {"1", "2"}
    assert hass.data["expiry_tracker_reminders_active"] is False
    assert "expiry_tracker_reminders_backend" not in hass.data
    assert manager._change_listener is None


async def test_reload_detaches_backend_without_deleting_remote_reminders(monkeypatch):
    calls: list[str] = []

    class ConfigEntries:
        async def async_unload_platforms(self, entry, platforms):
            calls.append("platforms")
            return True

    async def cleanup(hass, *, remove_remote=True):
        calls.append(f"cleanup:{remove_remote}")
        return True

    monkeypatch.setattr(expiry_tracker, "async_cleanup_reminders", cleanup)
    monkeypatch.setattr(
        expiry_tracker.frontend,
        "async_remove_panel",
        lambda *args, **kwargs: calls.append("panel"),
    )
    monkeypatch.setattr(
        expiry_tracker,
        "async_unregister_services",
        lambda hass: calls.append("services"),
    )
    hass = SimpleNamespace(config_entries=ConfigEntries(), data={})
    entry = SimpleNamespace(disabled_by=None)

    assert await expiry_tracker.async_unload_entry(hass, entry)
    assert calls == ["platforms", "cleanup:False", "panel", "services"]


async def test_disabled_entry_unload_removes_remote_reminders(monkeypatch):
    calls: list[str] = []

    class ConfigEntries:
        async def async_unload_platforms(self, entry, platforms):
            return True

    async def cleanup(hass, *, remove_remote=True):
        calls.append(f"cleanup:{remove_remote}")
        return True

    monkeypatch.setattr(expiry_tracker, "async_cleanup_reminders", cleanup)
    monkeypatch.setattr(expiry_tracker.frontend, "async_remove_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr(expiry_tracker, "async_unregister_services", lambda hass: None)
    hass = SimpleNamespace(config_entries=ConfigEntries(), data={})
    entry = SimpleNamespace(disabled_by="user")

    assert await expiry_tracker.async_unload_entry(hass, entry)
    assert calls == ["cleanup:True"]


async def test_switching_reminders_off_cleans_before_reload(monkeypatch):
    calls: list[str] = []

    class ConfigEntries:
        async def async_reload(self, entry_id):
            calls.append(f"reload:{entry_id}")

    async def cleanup(hass, *, remove_remote=True):
        calls.append(f"cleanup:{remove_remote}")
        return True

    monkeypatch.setattr(expiry_tracker, "async_cleanup_reminders", cleanup)
    hass = SimpleNamespace(config_entries=ConfigEntries(), data={})
    entry = SimpleNamespace(entry_id="entry-1", options={"use_reminders": False})

    await expiry_tracker._options_updated(hass, entry)
    assert calls == ["cleanup:True", "reload:entry-1"]


async def test_entry_removal_retries_remote_cleanup(monkeypatch):
    calls: list[str] = []

    async def cleanup(hass, *, remove_remote=True):
        calls.append(f"cleanup:{remove_remote}")
        return True

    monkeypatch.setattr(expiry_tracker, "async_cleanup_reminders", cleanup)
    hass = SimpleNamespace(data={})

    await expiry_tracker.async_remove_entry(hass, SimpleNamespace())
    assert calls == ["cleanup:True"]
