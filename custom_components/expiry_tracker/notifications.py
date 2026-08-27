"""Quiet notification/escalation scheduler using normal HA notify services."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .calculations import ExpiryStatus, calculate_state
from .const import CONF_NOTIFICATION_SERVICE, CONF_NOTIFICATION_TARGET
from .helpers import get_manager, local_today
from .models import ExpiryItem

_LOGGER = logging.getLogger(__name__)


def _notification_timestamp(value: str | None) -> datetime | None:
    """Parse a stored notification timestamp without breaking the delivery loop."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _current_event(item: ExpiryItem, status: ExpiryStatus, days: int) -> str | None:
    """Return only the most relevant milestone for the item's current state."""
    if status is ExpiryStatus.EXPIRED:
        return "expiry" if item.notify_expiry else None
    if status is ExpiryStatus.URGENT:
        return "urgent" if item.notify_urgent else None
    if status is ExpiryStatus.ACTIONABLE:
        return "actionable" if item.notify_actionable else None
    if status is ExpiryStatus.WARNING:
        crossed = [threshold for threshold in item.warning_thresholds if 0 <= days <= threshold]
        return f"warning_{min(crossed)}" if crossed else None
    return None


async def async_process_notifications(hass: HomeAssistant) -> None:
    """Send current transitions once and optionally repeat unacknowledged attention alerts."""
    entries = hass.config_entries.async_entries("expiry_tracker")
    if not entries:
        return
    if hass.data.get("expiry_tracker_reminders_active"):
        return
    configured = entries[0].options.get(CONF_NOTIFICATION_SERVICE, "").strip()
    if not configured or "." not in configured:
        return
    domain, service = configured.split(".", 1)
    now = datetime.now(UTC)
    today = local_today()
    manager = get_manager(hass)
    target = entries[0].options.get(CONF_NOTIFICATION_TARGET, "").strip()

    for item in manager.list_items():
        if not item.enabled:
            continue
        state = calculate_state(item, today)
        current_event = _current_event(item, state.status, state.days_until_expiry)
        last_notifications = item.last_notifications or {}
        events: list[str] = []

        if current_event and current_event not in last_notifications:
            events.append(current_event)
        elif item.repeat_until_acknowledged and state.requires_attention:
            previous_repeat = _notification_timestamp(last_notifications.get("attention_repeat"))
            stage_key = state.attention_stage.value if state.attention_stage else None
            previous_stage = _notification_timestamp(
                last_notifications.get(stage_key) if stage_key else None
            )
            previous_times = [
                value for value in (previous_repeat, previous_stage) if value is not None
            ]
            previous = max(previous_times) if previous_times else None
            if previous is None or now - previous >= timedelta(hours=item.repeat_interval_hours):
                events.append("attention_repeat")

        for event_key in events:
            data = {
                "title": f"Expiry Tracker: {item.name}",
                "message": (
                    f"{item.name} is {state.status.value}. "
                    f"Expiry: {item.expiry_date.isoformat()} ({state.days_until_expiry} days)."
                ),
            }
            if target:
                data["target"] = target
            try:
                await hass.services.async_call(domain, service, data, blocking=True)
                await manager.async_record_notification(
                    item.id, event_key, now.isoformat().replace("+00:00", "Z")
                )
            except Exception:  # One bad target/item must not block all remaining notifications.
                _LOGGER.warning(
                    "Could not deliver Expiry Tracker notification %s for item %s",
                    event_key,
                    item.id,
                    exc_info=True,
                )


def async_setup_notifications(hass: HomeAssistant, entry: object) -> CALLBACK_TYPE:
    """Check hourly; transition deduplication prevents repeated spam."""
    hass.async_create_task(
        async_process_notifications(hass), "expiry_tracker_initial_notifications"
    )

    async def scheduled(now: datetime) -> None:
        await async_process_notifications(hass)

    return async_track_time_interval(hass, scheduled, timedelta(hours=1))
