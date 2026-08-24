"""Optional, service-only bridge to the Reminders integration."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant

from .calculations import ExpiryStatus, calculate_state
from .const import (
    CONF_USE_REMINDERS,
    REMINDERS_DOMAIN,
    REMINDERS_LIFECYCLE_EVENT,
    REMINDERS_SOURCE,
)
from .helpers import local_today
from .manager import ExpiryTrackerManager
from .models import ExpiryItem, ItemNotFoundError

_LOGGER = logging.getLogger(__name__)
_SERVICES = ("create", "list", "update", "delete")


def reminders_available(hass: HomeAssistant) -> bool:
    """Check the public service contract; never import Reminders internals."""
    return all(hass.services.has_service(REMINDERS_DOMAIN, service) for service in _SERVICES)


class ReminderBackend:
    """Reconciles one-time, source-owned milestone reminders."""

    def __init__(self, hass: HomeAssistant, manager: ExpiryTrackerManager) -> None:
        self.hass = hass
        self.manager = manager

    def _milestones(self, item: ExpiryItem) -> dict[str, dict[str, Any]]:
        if not item.enabled:
            return {}
        today = local_today()
        state = calculate_state(item, today)
        dates: dict[str, date] = {
            **{f"warning_{days}": item.expiry_date - timedelta(days=days) for days in item.warning_thresholds},
            "actionable": state.actionable_date,
            "urgent": state.urgent_date,
            "expiry": item.expiry_date,
        }
        current = {
            ExpiryStatus.EXPIRED: "expiry",
            ExpiryStatus.URGENT: "urgent",
            ExpiryStatus.ACTIONABLE: "actionable",
        }.get(state.status)
        result: dict[str, dict[str, Any]] = {}
        for event, due_date in dates.items():
            if due_date < today or (due_date == today and event != current and state.status != ExpiryStatus.WARNING):
                continue
            if due_date == today and state.status == ExpiryStatus.WARNING and not event.startswith("warning_"):
                continue
            if event.startswith("warning_"):
                acknowledgement_policy: str = "not_required"
                escalation: dict[str, int] | None = None
            elif event == "actionable":
                acknowledgement_policy, escalation = "required", None
            elif event == "urgent":
                acknowledgement_policy = "required"
                escalation = {"initial_delay_minutes": 60, "repeat_minutes": 240, "max_attempts": 3}
            else:
                acknowledgement_policy = "required"
                escalation = {"initial_delay_minutes": 30, "repeat_minutes": 120, "max_attempts": 5}
            result[event] = {
                "title": f"Expiry Tracker: {item.name}",
                "message": f"{item.name}: {event.replace('_', ' ')}. Expires {item.expiry_date.isoformat()}.",
                "due": f"{due_date.isoformat()} 09:00:00",
                "acknowledgement_policy": acknowledgement_policy,
                "escalation": escalation,
                "source": REMINDERS_SOURCE,
                "source_id": item.id,
                "source_event": event,
                "managed_externally": True,
            }
        return result

    async def _call(self, service: str, data: dict[str, Any], *, response: bool = False) -> Any:
        return await self.hass.services.async_call(
            REMINDERS_DOMAIN, service, data, blocking=True, return_response=response
        )

    @staticmethod
    def _id(reminder: dict[str, Any]) -> str | None:
        value = reminder.get("id", reminder.get("reminder_id"))
        return str(value) if value else None

    @staticmethod
    def _matches(reminder: dict[str, Any], wanted: dict[str, Any]) -> bool:
        due = str(reminder.get("due", "")).replace("T", " ")
        return all(
            reminder.get(key) == wanted[key]
            for key in ("title", "message", "source", "source_id", "source_event", "managed_externally")
        ) and due.startswith(wanted["due"][:10])

    async def async_reconcile(self, item: ExpiryItem | None) -> None:
        if not reminders_available(self.hass) or item is None:
            return
        try:
            listed = await self._call("list", {"source": REMINDERS_SOURCE, "source_id": item.id}, response=True)
            existing = listed.get("reminders", []) if isinstance(listed, dict) else []
            expected = self._milestones(item)
            grouped: dict[str, list[dict[str, Any]]] = {}
            for reminder in existing:
                if reminder.get("source") == REMINDERS_SOURCE and reminder.get("source_id") == item.id:
                    grouped.setdefault(str(reminder.get("source_event")), []).append(reminder)
            for event, reminders in grouped.items():
                keep = sorted(reminders, key=lambda value: self._id(value) or "")[0] if reminders else None
                for duplicate in reminders[1:]:
                    if reminder_id := self._id(duplicate):
                        await self._call("delete", {"reminder_id": reminder_id})
                wanted = expected.pop(event, None)
                if keep and (reminder_id := self._id(keep)):
                    if wanted is None:
                        await self._call("delete", {"reminder_id": reminder_id})
                    elif not self._matches(keep, wanted):
                        await self._call("update", {"reminder_id": reminder_id, **wanted})
            for wanted in expected.values():
                await self._call("create", wanted)
        except Exception:  # A temporarily unavailable optional backend must not break items.
            _LOGGER.warning("Could not reconcile Expiry Tracker reminders", exc_info=True)

    async def async_removed(self, item: ExpiryItem) -> None:
        if not reminders_available(self.hass):
            return
        try:
            listed = await self._call("list", {"source": REMINDERS_SOURCE, "source_id": item.id}, response=True)
            for reminder in listed.get("reminders", []) if isinstance(listed, dict) else []:
                if reminder.get("source") == REMINDERS_SOURCE and reminder.get("source_id") == item.id:
                    if reminder_id := self._id(reminder):
                        await self._call("delete", {"reminder_id": reminder_id})
        except Exception:
            _LOGGER.warning("Could not remove Expiry Tracker reminders", exc_info=True)

    async def async_changed(self, action: str, item: ExpiryItem | None) -> None:
        if item is None:
            return
        if action == "delete":
            await self.async_removed(item)
        else:
            await self.async_reconcile(item)

    async def async_reconcile_all(self) -> None:
        for item in self.manager.list_items():
            await self.async_reconcile(item)

    async def async_lifecycle(self, event: Event[Any]) -> None:
        data = event.data
        if data.get("source") != REMINDERS_SOURCE or data.get("action") != "acknowledged":
            return
        item_id = data.get("source_id")
        if not isinstance(item_id, str):
            return
        try:
            await self.manager.async_acknowledge(item_id)
        except ItemNotFoundError:
            return


async def async_setup_reminders(hass: HomeAssistant, entry: Any, manager: ExpiryTrackerManager) -> CALLBACK_TYPE | None:
    """Enable the adapter only when opted in and the public contract exists."""
    if not entry.options.get(CONF_USE_REMINDERS, False) or not reminders_available(hass):
        hass.data["expiry_tracker_reminders_active"] = False
        return None
    backend = ReminderBackend(hass, manager)
    manager.set_change_listener(backend.async_changed)
    hass.data["expiry_tracker_reminders_active"] = True
    await backend.async_reconcile_all()
    return hass.bus.async_listen(REMINDERS_LIFECYCLE_EVENT, backend.async_lifecycle)
