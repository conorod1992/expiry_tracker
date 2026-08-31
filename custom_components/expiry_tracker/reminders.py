"""Optional, service-only bridge to the Reminders integration."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from homeassistant.core import CALLBACK_TYPE, Context, Event, HomeAssistant

from .calculations import AttentionStage, add_months, calculate_state, subtract_days
from .const import (
    CONF_USE_REMINDERS,
    REMINDERS_DOMAIN,
    REMINDERS_LIFECYCLE_EVENT,
    REMINDERS_SOURCE,
    RENEWAL_REQUESTED_EVENT,
)
from .helpers import local_today
from .manager import ExpiryTrackerManager
from .models import ExpiryItem, ItemNotFoundError

_LOGGER = logging.getLogger(__name__)
_SERVICES = ("create", "list", "update", "delete", "external_action")
_COMPLETED_LABELS = {
    "renew": "Renewed",
    "replace": "Replaced",
    "review": "Reviewed",
    "retest": "Re-tested",
    "reregister": "Re-registered",
    "cancel": "Cancelled",
    "check": "Checked",
}
_MAX_EXTERNAL_ACTION_LABEL = 64
_ACTIVE_DATA_KEY = "expiry_tracker_reminders_active"
_BACKEND_DATA_KEY = "expiry_tracker_reminders_backend"


def _completion_label(item: ExpiryItem) -> str:
    if item.action_type == "custom":
        label = item.custom_action_label or "Completed"
    else:
        label = _COMPLETED_LABELS.get(item.action_type, "Renewed")
    return label[:_MAX_EXTERNAL_ACTION_LABEL].rstrip()


def _completion_action(item: ExpiryItem) -> dict[str, str]:
    return {"id": "renewed", "label": _completion_label(item)}


def _stage_notifications_enabled(item: ExpiryItem, event: str | None) -> bool:
    """Return whether an attention milestone is enabled for this item."""
    if event == AttentionStage.ACTIONABLE.value:
        return item.notify_actionable
    if event == AttentionStage.URGENT.value:
        return item.notify_urgent
    if event == AttentionStage.EXPIRY.value:
        return item.notify_expiry
    return False


def reminders_available(hass: HomeAssistant) -> bool:
    """Check the public service contract; never import Reminders internals."""
    return all(hass.services.has_service(REMINDERS_DOMAIN, service) for service in _SERVICES)


async def _owner_user_id(hass: HomeAssistant) -> str | None:
    """Resolve the single active Home Assistant owner for Reminders ownership."""
    users = await hass.auth.async_get_users()
    owners = [
        user.id for user in users if user.is_owner and user.is_active and not user.system_generated
    ]
    if len(owners) != 1:
        _LOGGER.warning(
            "Could not resolve exactly one active Home Assistant owner for Expiry Tracker Reminders"
        )
        return None
    return owners[0]


class ReminderBackend:
    """Reconciles one-time, source-owned milestone reminders."""

    def __init__(
        self, hass: HomeAssistant, manager: ExpiryTrackerManager, owner_user_id: str
    ) -> None:
        self.hass = hass
        self.manager = manager
        self.owner_user_id = owner_user_id

    def _milestones(self, item: ExpiryItem) -> dict[str, dict[str, Any]]:
        if not item.enabled or item.closed:
            return {}
        today = local_today()
        state = calculate_state(item, today)
        dates: dict[str, date] = {
            f"warning_{days}": subtract_days(item.expiry_date, days)
            for days in item.warning_thresholds
        }
        if item.notify_expiry:
            dates["expiry"] = item.expiry_date
        if item.requires_action:
            if item.notify_actionable:
                dates["actionable"] = state.actionable_date
            if item.notify_urgent:
                dates["urgent"] = state.urgent_date
        current = state.attention_stage.value if state.attention_stage else None
        enabled_current = current if _stage_notifications_enabled(item, current) else None
        result: dict[str, dict[str, Any]] = {}
        for event, due_date in dates.items():
            warning = event.startswith("warning_")
            passive_expiry = event == "expiry" and not item.requires_action
            if warning and (
                due_date < today or (due_date == today and enabled_current is not None)
            ):
                continue
            if not warning and not passive_expiry and due_date <= today and event != current:
                continue
            if passive_expiry and due_date < today:
                continue
            scheduled_date = today if event == current and due_date < today else due_date
            if warning or passive_expiry:
                acknowledgement_policy: str = "not_required"
                escalation: dict[str, int] | None = None
                external_actions: list[dict[str, str]] = []
            elif event == "actionable":
                acknowledgement_policy = "required"
                escalation = {
                    "initial_delay_minutes": 240,
                    "repeat_minutes": 720,
                    "max_attempts": 2,
                }
                external_actions = [_completion_action(item)]
            elif event == "urgent":
                acknowledgement_policy = "required"
                escalation = {
                    "initial_delay_minutes": 60,
                    "repeat_minutes": 240,
                    "max_attempts": 3,
                }
                external_actions = [_completion_action(item)]
            else:
                acknowledgement_policy = "required"
                escalation = {
                    "initial_delay_minutes": 30,
                    "repeat_minutes": 120,
                    "max_attempts": 5,
                }
                external_actions = [_completion_action(item)]
            result[event] = {
                "title": f"Expiry Tracker: {item.name}",
                "message": (
                    f"{item.name}: {event.replace('_', ' ')}. "
                    f"Expires {item.expiry_date.isoformat()}."
                ),
                "due": f"{scheduled_date.isoformat()} 09:00:00",
                "acknowledgement_policy": acknowledgement_policy,
                "allow_manual_completion": False,
                "escalation": escalation,
                "external_actions": external_actions,
                "source": REMINDERS_SOURCE,
                "source_id": item.id,
                "source_event": event,
                "managed_externally": True,
            }
        return result

    async def _call(self, service: str, data: dict[str, Any], *, response: bool = False) -> Any:
        payload = dict(data)
        if service in {"create", "list"}:
            payload.setdefault("user_id", self.owner_user_id)
        return await self.hass.services.async_call(
            REMINDERS_DOMAIN,
            service,
            payload,
            blocking=True,
            context=Context(user_id=self.owner_user_id),
            return_response=response,
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
            for key in (
                "title",
                "message",
                "acknowledgement_policy",
                "allow_manual_completion",
                "escalation",
                "external_actions",
                "source",
                "source_id",
                "source_event",
                "managed_externally",
            )
        ) and due.startswith(wanted["due"][:10])

    async def async_reconcile(self, item: ExpiryItem | None) -> bool:
        if not reminders_available(self.hass) or item is None:
            return False
        try:
            listed = await self._call(
                "list", {"source": REMINDERS_SOURCE, "source_id": item.id}, response=True
            )
            existing = listed.get("reminders", []) if isinstance(listed, dict) else []
            expected = self._milestones(item)
            grouped: dict[str, list[dict[str, Any]]] = {}
            for reminder in existing:
                if (
                    reminder.get("source") == REMINDERS_SOURCE
                    and reminder.get("source_id") == item.id
                ):
                    grouped.setdefault(str(reminder.get("source_event")), []).append(reminder)
            for event, reminders in grouped.items():
                keep = min(
                    reminders,
                    key=lambda value: (self._id(value) is None, self._id(value) or ""),
                )
                for duplicate in reminders:
                    if duplicate is keep:
                        continue
                    if reminder_id := self._id(duplicate):
                        await self._call("delete", {"reminder_id": reminder_id})
                wanted = expected.pop(event, None)
                if reminder_id := self._id(keep):
                    if wanted is None:
                        await self._call("delete", {"reminder_id": reminder_id})
                    elif not self._matches(keep, wanted):
                        await self._call("update", {"reminder_id": reminder_id, **wanted})
                elif wanted is not None:
                    expected[event] = wanted
            for wanted in expected.values():
                await self._call("create", wanted)
            return True
        except Exception:  # A temporarily unavailable optional backend must not break items.
            _LOGGER.warning("Could not reconcile Expiry Tracker reminders", exc_info=True)
            return False

    async def async_removed(self, item: ExpiryItem) -> bool:
        if not reminders_available(self.hass):
            return False
        try:
            listed = await self._call(
                "list", {"source": REMINDERS_SOURCE, "source_id": item.id}, response=True
            )
            for reminder in listed.get("reminders", []) if isinstance(listed, dict) else []:
                if (
                    reminder.get("source") == REMINDERS_SOURCE
                    and reminder.get("source_id") == item.id
                    and (reminder_id := self._id(reminder))
                ):
                    await self._call("delete", {"reminder_id": reminder_id})
            return True
        except Exception:
            _LOGGER.warning("Could not remove Expiry Tracker reminders", exc_info=True)
            return False

    async def async_remove_all(self) -> bool:
        """Remove every reminder owned by this Expiry Tracker backend."""
        if not reminders_available(self.hass):
            return False
        try:
            listed = await self._call("list", {"source": REMINDERS_SOURCE}, response=True)
            if not isinstance(listed, dict) or not isinstance(listed.get("reminders"), list):
                raise ValueError("reminders.list returned an invalid response")
            for reminder in listed["reminders"]:
                if reminder.get("source") == REMINDERS_SOURCE and (
                    reminder_id := self._id(reminder)
                ):
                    await self._call("delete", {"reminder_id": reminder_id})
            return True
        except Exception:
            _LOGGER.warning("Could not remove all Expiry Tracker reminders", exc_info=True)
            return False

    async def async_changed(self, action: str, item: ExpiryItem | None) -> None:
        if item is None:
            return
        success = (
            await self.async_removed(item)
            if action == "delete"
            else await self.async_reconcile(item)
        )
        if not success:
            self.hass.data[_ACTIVE_DATA_KEY] = False
            self.manager.set_change_listener(None)
            _LOGGER.warning(
                "Expiry Tracker disabled Reminders delivery after reconciliation failed; "
                "built-in notifications remain available"
            )

    async def async_reconcile_all(self) -> bool:
        """Verify owner access and reconcile every active Expiry Tracker item."""
        try:
            listed = await self._call("list", {"source": REMINDERS_SOURCE}, response=True)
            if not isinstance(listed, dict) or not isinstance(listed.get("reminders"), list):
                raise ValueError("reminders.list returned an invalid response")
        except Exception:
            _LOGGER.warning(
                "Could not verify Expiry Tracker access to the Reminders owner", exc_info=True
            )
            return False
        for item in self.manager.list_items():
            if not await self.async_reconcile(item):
                return False
        return True

    async def async_lifecycle(self, event: Event[Any]) -> None:
        if not self.hass.data.get(_ACTIVE_DATA_KEY):
            return
        data = event.data
        if data.get("source") != REMINDERS_SOURCE:
            return
        item_id = data.get("source_id")
        source_event = data.get("source_event")
        if not isinstance(item_id, str) or source_event not in {
            stage.value for stage in AttentionStage
        }:
            return
        try:
            item = self.manager.get_item(item_id)
        except ItemNotFoundError:
            return
        if item.closed or not item.requires_action:
            return
        if data.get("external_action_id") == "renewed":
            if item.action_type == "cancel":
                await self.manager.async_close(item.id, "Marked as cancelled")
            else:
                await self._request_renewal(item)
        elif data.get("action") in {"dismissed", "acknowledged"}:
            await self.manager.async_acknowledge(item_id, stage=source_event)

    async def _request_renewal(self, item: ExpiryItem) -> None:
        """Guide the user to confirmation; an external action never changes the date silently."""
        suggested = None
        if item.recurrence_months:
            suggested_date = add_months(item.expiry_date, item.recurrence_months)
            today = local_today()
            while suggested_date <= today:
                suggested_date = add_months(suggested_date, item.recurrence_months)
            suggested = suggested_date.isoformat()
        self.hass.bus.async_fire(
            RENEWAL_REQUESTED_EVENT,
            {"item_id": item.id, "suggested_expiry_date": suggested},
        )
        completion = _completion_label(item)
        await self.hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "notification_id": f"expiry_tracker_renewal_{item.id}",
                "title": f"Confirm {completion.lower()}: {item.name}",
                "message": (
                    f"{completion} was selected, but the expiry has not changed. "
                    f"[Open Expiry Tracker to confirm the new date](/expiry-tracker?renew={item.id})."
                ),
            },
            blocking=True,
        )


async def async_cleanup_reminders(hass: HomeAssistant, *, remove_remote: bool = True) -> bool:
    """Deactivate the backend and optionally remove all source-owned reminders."""
    hass.data[_ACTIVE_DATA_KEY] = False
    backend = hass.data.get(_BACKEND_DATA_KEY)
    if not isinstance(backend, ReminderBackend):
        return True
    backend.manager.set_change_listener(None)
    if not remove_remote:
        return True
    if not await backend.async_remove_all():
        return False
    hass.data.pop(_BACKEND_DATA_KEY, None)
    return True


async def async_setup_reminders(
    hass: HomeAssistant, entry: Any, manager: ExpiryTrackerManager
) -> CALLBACK_TYPE | None:
    """Enable the adapter only after its owner and public service contract are verified."""
    hass.data[_ACTIVE_DATA_KEY] = False
    previous_backend = hass.data.get(_BACKEND_DATA_KEY)
    if not entry.options.get(CONF_USE_REMINDERS, False):
        if isinstance(previous_backend, ReminderBackend):
            await async_cleanup_reminders(hass)
            return None
        if not reminders_available(hass):
            return None
        owner_user_id = await _owner_user_id(hass)
        if owner_user_id is None:
            return None
        cleanup_backend = ReminderBackend(hass, manager, owner_user_id)
        hass.data[_BACKEND_DATA_KEY] = cleanup_backend
        if await cleanup_backend.async_remove_all():
            hass.data.pop(_BACKEND_DATA_KEY, None)
        return None
    hass.data.pop(_BACKEND_DATA_KEY, None)
    if not reminders_available(hass):
        return None
    owner_user_id = await _owner_user_id(hass)
    if owner_user_id is None:
        return None
    backend = ReminderBackend(hass, manager, owner_user_id)
    if not await backend.async_reconcile_all():
        return None
    manager.set_change_listener(backend.async_changed)
    hass.data[_BACKEND_DATA_KEY] = backend
    hass.data[_ACTIVE_DATA_KEY] = True
    return hass.bus.async_listen(REMINDERS_LIFECYCLE_EVENT, backend.async_lifecycle)
