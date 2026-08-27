"""Read-only contributed LLM tools."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

import voluptuous as vol
from homeassistant.components import llm as llm_component
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import llm
from homeassistant.helpers.llm import LLMContext, ToolInput

from .calculations import calculate_state
from .helpers import decorate, get_manager, local_today
from .models import ExpiryItem

_QUERY_VIEWS = (
    "all",
    "next_expiry",
    "next_actionable",
    "recently_completed",
    "expiring_this_year",
    "dismissed_outstanding",
)


def _completion_at(item: ExpiryItem) -> datetime | None:
    """Return the most recent recorded real-world completion timestamp."""
    latest: datetime | None = None
    for event in item.history:
        completed = event.get("type") == "renewed" or (
            event.get("type") == "closed" and event.get("reason") == "Marked as cancelled"
        )
        if not completed or not isinstance(event.get("at"), str):
            continue
        try:
            parsed = datetime.fromisoformat(event["at"].replace("Z", "+00:00"))
        except ValueError:
            continue
        parsed = parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
        if latest is None or parsed > latest:
            latest = parsed
    return latest


def _view_items(
    items: list[ExpiryItem],
    today: date,
    view: str,
    *,
    recent_days: int = 90,
) -> list[dict[str, Any]]:
    """Apply one natural-language-oriented read-only view."""
    active = [item for item in items if item.enabled and not item.closed]

    if view == "next_expiry":
        selected = sorted(
            (item for item in active if item.expiry_date >= today),
            key=lambda item: (item.expiry_date, item.name.casefold(), item.id),
        )
        return [decorate(item, today) for item in selected]

    if view == "next_actionable":
        eligible: list[tuple[tuple[int, date, date, str, str], ExpiryItem]] = []
        for item in active:
            if not item.requires_action:
                continue
            state = calculate_state(item, today)
            key = (
                0 if state.actionable else 1,
                item.expiry_date if state.actionable else state.actionable_date,
                item.expiry_date,
                item.name.casefold(),
                item.id,
            )
            eligible.append((key, item))
        return [decorate(item, today) for _, item in sorted(eligible, key=lambda row: row[0])]

    if view == "recently_completed":
        cutoff = datetime.combine(today - timedelta(days=recent_days), datetime.min.time(), UTC)
        completed: list[tuple[datetime, ExpiryItem]] = []
        for item in items:
            completed_at = _completion_at(item)
            if completed_at is not None and completed_at >= cutoff:
                completed.append((completed_at, item))
        completed.sort(key=lambda row: (row[0], row[1].name.casefold()), reverse=True)
        result = []
        for completed_at, item in completed:
            decorated = decorate(item, today)
            decorated["last_completed_at"] = completed_at.isoformat().replace("+00:00", "Z")
            result.append(decorated)
        return result

    if view == "expiring_this_year":
        selected = sorted(
            (item for item in active if item.expiry_date.year == today.year),
            key=lambda item: (item.expiry_date, item.name.casefold(), item.id),
        )
        return [decorate(item, today) for item in selected]

    if view == "dismissed_outstanding":
        selected: list[tuple[date, ExpiryItem]] = []
        for item in active:
            state = calculate_state(item, today)
            if item.requires_action and state.actionable and state.acknowledged:
                selected.append((item.expiry_date, item))
        selected.sort(key=lambda row: (row[0], row[1].name.casefold(), row[1].id))
        return [decorate(item, today) for _, item in selected]

    return [decorate(item, today) for item in active]


class QueryExpiryItemsTool(llm.Tool):
    name = "query_expiry_items"
    description = (
        "Read local Expiry Tracker records. Use view=next_expiry for upcoming expiries, "
        "next_actionable for what can be dealt with now/next, recently_completed for recent "
        "renewals/completions, expiring_this_year for the current calendar year, or "
        "dismissed_outstanding for items whose current reminder was dismissed but the task "
        "is still incomplete. Use view=all for ordinary search/filter queries. Read-only."
    )
    parameters = vol.Schema(
        {
            vol.Optional("view", default="all"): vol.In(_QUERY_VIEWS),
            vol.Optional("query", default=""): cv.string,
            vol.Optional("actionable_only", default=False): cv.boolean,
            vol.Optional("urgent_only", default=False): cv.boolean,
            vol.Optional("expired_only", default=False): cv.boolean,
            vol.Optional("due_within_days"): vol.All(vol.Coerce(int), vol.Range(min=0, max=36500)),
            vol.Optional("recent_completed_days", default=90): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=3650)
            ),
            vol.Optional("category"): cv.string,
            vol.Optional("important_only", default=False): cv.boolean,
            vol.Optional("limit", default=25): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
        }
    )

    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> dict[str, Any]:
        args = tool_input.tool_args
        today = local_today()
        manager = get_manager(hass)
        candidates = (
            manager.search(args["query"], limit=500)
            if args["query"]
            else manager.list_items()
        )
        if category := args.get("category"):
            candidates = [item for item in candidates if item.category == category]
        if args["important_only"]:
            candidates = [item for item in candidates if item.important]

        view = args["view"]
        if view != "all":
            result = _view_items(
                candidates,
                today,
                view,
                recent_days=args["recent_completed_days"],
            )[: args["limit"]]
            return {"view": view, "items": result, "count": len(result)}

        ids = {item.id for item in candidates}
        end = (
            today + timedelta(days=args["due_within_days"])
            if "due_within_days" in args
            else None
        )
        rows = manager.query(
            today,
            end=end,
            actionable_only=args["actionable_only"],
            urgent_only=args["urgent_only"],
            expired_only=args["expired_only"],
            category=args.get("category"),
            important_only=args["important_only"],
            limit=500,
        )
        result = [decorate(item, today) for item, _ in rows if item.id in ids][: args["limit"]]
        return {"view": view, "items": result, "count": len(result)}


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> llm_component.LLMTools:
    return llm_component.LLMTools(
        tools=[QueryExpiryItemsTool()],
        prompt=(
            "Expiry Tracker is local and strictly read-only. Prefer the named query views when "
            "the question matches them: next_expiry, next_actionable, recently_completed, "
            "expiring_this_year, or dismissed_outstanding. Warning means advance notice only. "
            "Actionable means the configured action window has begun. Dismissing a reminder "
            "does not complete the real-world task. Urgent outranks actionable; expired outranks "
            "urgent. For other questions use view=all with the existing filters."
        ),
    )
