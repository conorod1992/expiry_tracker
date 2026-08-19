"""Read-only contributed LLM tools."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import voluptuous as vol
from homeassistant.components import llm as llm_component
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import llm
from homeassistant.helpers.llm import LLMContext, ToolInput

from .helpers import decorate, get_manager, local_today


class QueryExpiryItemsTool(llm.Tool):
    name = "query_expiry_items"
    description = "Search local expiry records and answer when something expires or becomes actionable. For 'what needs attention', set actionable_only=true. Supports urgent, expired, date horizon, category, and important filters. Read-only."
    parameters = vol.Schema(
        {
            vol.Optional("query", default=""): cv.string,
            vol.Optional("actionable_only", default=False): cv.boolean,
            vol.Optional("urgent_only", default=False): cv.boolean,
            vol.Optional("expired_only", default=False): cv.boolean,
            vol.Optional("due_within_days"): vol.All(vol.Coerce(int), vol.Range(min=0, max=36500)),
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
        candidates = (
            get_manager(hass).search(args["query"], limit=500)
            if args["query"]
            else get_manager(hass).list_items()
        )
        ids = {item.id for item in candidates}
        end = today + timedelta(days=args["due_within_days"]) if "due_within_days" in args else None
        rows = get_manager(hass).query(
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
        return {"items": result, "count": len(result)}


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> llm_component.LLMTools:
    return llm_component.LLMTools(
        tools=[QueryExpiryItemsTool()],
        prompt="Expiry Tracker is local and read-only. Warning means advance notice only. Actionable means the configured action window has begun. Urgent outranks actionable; expired outranks urgent. For questions like 'what admin do I need to deal with?', query actionable_only so future non-actionable expiries are excluded.",
    )
