"""Quiet notification/escalation scheduler using normal HA notify services."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .calculations import calculate_state
from .const import CONF_NOTIFICATION_SERVICE, CONF_NOTIFICATION_TARGET
from .helpers import get_manager, local_today


async def async_process_notifications(hass: HomeAssistant) -> None:
    """Send each transition once; optionally repeat attention alerts at a bounded interval."""
    entries = hass.config_entries.async_entries("expiry_tracker")
    if not entries:
        return
    configured = entries[0].options.get(CONF_NOTIFICATION_SERVICE, "").strip()
    if not configured or "." not in configured:
        return
    domain, service = configured.split(".", 1)
    now = datetime.now(UTC)
    today = local_today()
    manager = get_manager(hass)
    for item in manager.list_items():
        if not item.enabled:
            continue
        state = calculate_state(item, today)
        events: list[str] = []
        days = state.days_until_expiry
        for threshold in item.warning_thresholds:
            if 0 <= days <= threshold:
                events.append(f"warning_{threshold}")
        if today >= state.actionable_date and item.notify_actionable:
            events.append("actionable")
        if today >= state.urgent_date and item.notify_urgent:
            events.append("urgent")
        if today >= item.expiry_date and item.notify_expiry:
            events.append("expiry")
        if item.repeat_until_acknowledged and state.requires_attention:
            events.append("attention_repeat")
        for event_key in events:
            previous = (item.last_notifications or {}).get(event_key)
            if previous:
                previous_dt = datetime.fromisoformat(previous.replace("Z", "+00:00"))
                interval = item.repeat_interval_hours if event_key == "attention_repeat" else 10**9
                if now - previous_dt < timedelta(hours=interval):
                    continue
            target = entries[0].options.get(CONF_NOTIFICATION_TARGET, "").strip()
            data = {
                "title": f"Expiry Tracker: {item.name}",
                "message": f"{item.name} is {state.status.value}. Expiry: {item.expiry_date.isoformat()} ({days} days).",
            }
            if target:
                data["target"] = target
            await hass.services.async_call(domain, service, data, blocking=True)
            await manager.async_record_notification(
                item.id, event_key, now.isoformat().replace("+00:00", "Z")
            )


def async_setup_notifications(hass: HomeAssistant, entry: object) -> CALLBACK_TYPE:
    """Check hourly; transition deduplication prevents repeated spam."""
    hass.async_create_task(
        async_process_notifications(hass), "expiry_tracker_initial_notifications"
    )

    async def scheduled(now: datetime) -> None:
        await async_process_notifications(hass)

    return async_track_time_interval(hass, scheduled, timedelta(hours=1))
