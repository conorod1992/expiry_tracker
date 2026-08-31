"""Regression tests for native notification delivery."""

from datetime import date
from types import SimpleNamespace

from custom_components.expiry_tracker.manager import ExpiryTrackerManager
from custom_components.expiry_tracker.notifications import async_process_notifications

from .conftest import MemoryStorage, item_data


class ConfigEntries:
    def __init__(self, options):
        self.entry = SimpleNamespace(options=options)

    def async_entries(self, domain):
        assert domain == "expiry_tracker"
        return [self.entry]


class Services:
    def __init__(self, *, fail_first=False, reminders_available=False):
        self.calls = []
        self.fail_first = fail_first
        self.reminders_available = reminders_available

    def has_service(self, domain, service):
        return domain == "reminders" and self.reminders_available

    async def async_call(self, domain, service, data, **kwargs):
        self.calls.append((domain, service, data, kwargs))
        if self.fail_first and len(self.calls) == 1:
            raise RuntimeError("notification target unavailable")


def hass_for(manager, *, fail_first=False, reminders_active=False, reminders_available=False):
    return SimpleNamespace(
        config_entries=ConfigEntries({"notification_service": "notify.mobile_app"}),
        data={"expiry_tracker_reminders_active": reminders_active},
        services=Services(
            fail_first=fail_first,
            reminders_available=reminders_available,
        ),
        manager=manager,
    )


async def test_already_urgent_item_sends_only_current_milestone(monkeypatch):
    manager = ExpiryTrackerManager(MemoryStorage(), lambda: None)
    await manager.async_load()
    item = await manager.async_create_item(
        item_data(expiry_date="2026-08-27", warning_thresholds=[180, 90, 30, 7, 1])
    )
    hass = hass_for(manager)
    monkeypatch.setattr(
        "custom_components.expiry_tracker.notifications.local_today", lambda: date(2026, 8, 24)
    )
    monkeypatch.setattr(
        "custom_components.expiry_tracker.notifications.get_manager", lambda _hass: manager
    )

    await async_process_notifications(hass)

    assert len(hass.services.calls) == 1
    assert set(manager.get_item(item.id).last_notifications or {}) == {"urgent"}


async def test_expiry_day_sends_expiry_milestone(monkeypatch):
    manager = ExpiryTrackerManager(MemoryStorage(), lambda: None)
    await manager.async_load()
    item = await manager.async_create_item(item_data(expiry_date="2026-08-27"))
    hass = hass_for(manager)
    monkeypatch.setattr(
        "custom_components.expiry_tracker.notifications.local_today", lambda: date(2026, 8, 27)
    )
    monkeypatch.setattr(
        "custom_components.expiry_tracker.notifications.get_manager", lambda _hass: manager
    )

    await async_process_notifications(hass)

    assert len(hass.services.calls) == 1
    assert set(manager.get_item(item.id).last_notifications or {}) == {"expiry"}
    assert "expires today" in hass.services.calls[0][2]["message"]


async def test_native_delivery_falls_back_if_reminders_services_disappear(monkeypatch):
    manager = ExpiryTrackerManager(MemoryStorage(), lambda: None)
    await manager.async_load()
    item = await manager.async_create_item(item_data(expiry_date="2026-08-27"))
    hass = hass_for(manager, reminders_active=True, reminders_available=False)
    monkeypatch.setattr(
        "custom_components.expiry_tracker.notifications.local_today", lambda: date(2026, 8, 24)
    )
    monkeypatch.setattr(
        "custom_components.expiry_tracker.notifications.get_manager", lambda _hass: manager
    )

    await async_process_notifications(hass)

    assert len(hass.services.calls) == 1
    assert set(manager.get_item(item.id).last_notifications or {}) == {"urgent"}


async def test_warning_catch_up_uses_only_latest_crossed_threshold(monkeypatch):
    manager = ExpiryTrackerManager(MemoryStorage(), lambda: None)
    await manager.async_load()
    item = await manager.async_create_item(
        item_data(
            expiry_date="2026-09-01",
            actionable_offset_value=5,
            urgent_days_before=2,
            warning_thresholds=[180, 90, 30, 7, 1],
        )
    )
    hass = hass_for(manager)
    monkeypatch.setattr(
        "custom_components.expiry_tracker.notifications.local_today", lambda: date(2026, 8, 24)
    )
    monkeypatch.setattr(
        "custom_components.expiry_tracker.notifications.get_manager", lambda _hass: manager
    )

    await async_process_notifications(hass)

    assert len(hass.services.calls) == 1
    assert set(manager.get_item(item.id).last_notifications or {}) == {"warning_30"}


async def test_notification_failure_does_not_block_later_items(monkeypatch):
    manager = ExpiryTrackerManager(MemoryStorage(), lambda: None)
    await manager.async_load()
    first = await manager.async_create_item(item_data(name="A item", expiry_date="2026-08-27"))
    second = await manager.async_create_item(item_data(name="B item", expiry_date="2026-08-27"))
    hass = hass_for(manager, fail_first=True)
    monkeypatch.setattr(
        "custom_components.expiry_tracker.notifications.local_today", lambda: date(2026, 8, 24)
    )
    monkeypatch.setattr(
        "custom_components.expiry_tracker.notifications.get_manager", lambda _hass: manager
    )

    await async_process_notifications(hass)

    assert len(hass.services.calls) == 2
    assert not manager.get_item(first.id).last_notifications
    assert set(manager.get_item(second.id).last_notifications or {}) == {"urgent"}


async def test_malformed_notification_timestamp_does_not_break_repeats(monkeypatch):
    manager = ExpiryTrackerManager(MemoryStorage(), lambda: None)
    await manager.async_load()
    item = await manager.async_create_item(
        item_data(
            actionable_mode="immediate",
            urgent_days_before=0,
            require_acknowledgement=True,
            repeat_until_acknowledged=True,
            last_notifications={"actionable": "not-a-timestamp"},
        )
    )
    hass = hass_for(manager)
    monkeypatch.setattr(
        "custom_components.expiry_tracker.notifications.local_today", lambda: date(2026, 8, 24)
    )
    monkeypatch.setattr(
        "custom_components.expiry_tracker.notifications.get_manager", lambda _hass: manager
    )

    await async_process_notifications(hass)

    assert len(hass.services.calls) == 1
    assert "attention_repeat" in (manager.get_item(item.id).last_notifications or {})


async def test_hidden_repeat_does_not_bypass_require_dismissal(monkeypatch):
    manager = ExpiryTrackerManager(MemoryStorage(), lambda: None)
    await manager.async_load()
    await manager.async_create_item(
        item_data(
            actionable_mode="immediate",
            urgent_days_before=0,
            require_acknowledgement=False,
            repeat_until_acknowledged=True,
            last_notifications={"actionable": "2026-08-20T00:00:00Z"},
        )
    )
    hass = hass_for(manager)
    monkeypatch.setattr(
        "custom_components.expiry_tracker.notifications.local_today", lambda: date(2026, 8, 24)
    )
    monkeypatch.setattr(
        "custom_components.expiry_tracker.notifications.get_manager", lambda _hass: manager
    )

    await async_process_notifications(hass)

    assert hass.services.calls == []


async def test_repeat_respects_current_stage_notification_toggle(monkeypatch):
    manager = ExpiryTrackerManager(MemoryStorage(), lambda: None)
    await manager.async_load()
    await manager.async_create_item(
        item_data(
            expiry_date="2026-09-30",
            actionable_mode="immediate",
            urgent_days_before=7,
            notify_actionable=False,
            require_acknowledgement=True,
            repeat_until_acknowledged=True,
            last_notifications={"actionable": "2026-08-20T00:00:00Z"},
        )
    )
    hass = hass_for(manager)
    monkeypatch.setattr(
        "custom_components.expiry_tracker.notifications.local_today", lambda: date(2026, 8, 24)
    )
    monkeypatch.setattr(
        "custom_components.expiry_tracker.notifications.get_manager", lambda _hass: manager
    )

    await async_process_notifications(hass)

    assert hass.services.calls == []
