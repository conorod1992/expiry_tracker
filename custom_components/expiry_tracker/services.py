"""Structured Home Assistant actions with response data."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, NoReturn

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .helpers import decorate, get_manager, local_today, parse_date
from .models import ItemNotFoundError, ItemValidationError
from .schema import CREATE_FIELDS, UPDATE_FIELDS

DOMAIN = "expiry_tracker"
MUTATIONS = (
    "create_item",
    "update_item",
    "delete_item",
    "renew_item",
    "close_item",
    "reopen_item",
    "acknowledge_item",
    "reset_acknowledgement",
)
QUERIES = (
    "search_items",
    "get_upcoming",
    "get_actionable",
    "get_urgent",
    "get_expired",
    "get_between",
)
_UPDATE_KEYS = {str(key.schema) for key in UPDATE_FIELDS}


def _error(err: Exception) -> NoReturn:
    if isinstance(err, ItemNotFoundError):
        raise HomeAssistantError(f"Unknown expiry item ID: {err.args[0]}") from err
    raise HomeAssistantError(str(err)) from err


def _query(call: ServiceCall, **fixed: bool) -> dict[str, Any]:
    today = local_today()
    start = parse_date(call.data["start"], "start") if "start" in call.data else None
    end = parse_date(call.data["end"], "end") if "end" in call.data else None
    if end and start and end < start:
        raise HomeAssistantError("end must not be before start")
    if "days" in call.data:
        start, end = today, today + timedelta(days=call.data["days"])
    rows = get_manager(call.hass).query(
        today,
        start=start,
        end=end,
        category=call.data.get("category"),
        important_only=call.data.get("important_only", False),
        limit=call.data.get("limit", 100),
        **fixed,
    )
    return {"items": [decorate(item, today) for item, _ in rows], "count": len(rows)}


async def async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, "create_item"):
        return

    async def create(call: ServiceCall) -> dict[str, Any]:
        try:
            return {"item": decorate(await get_manager(hass).async_create_item(call.data))}
        except ItemValidationError as err:
            _error(err)

    async def update(call: ServiceCall) -> dict[str, Any]:
        try:
            changes = {key: value for key, value in call.data.items() if key in _UPDATE_KEYS}
            return {
                "item": decorate(
                    await get_manager(hass).async_update_item(call.data["item_id"], changes)
                )
            }
        except (ItemNotFoundError, ItemValidationError) as err:
            _error(err)

    async def delete(call: ServiceCall) -> dict[str, Any]:
        try:
            item = await get_manager(hass).async_delete_item(call.data["item_id"])
            return {"deleted": True, "item_id": item.id}
        except ItemNotFoundError as err:
            _error(err)

    async def renew(call: ServiceCall) -> dict[str, Any]:
        try:
            new_date = (
                parse_date(call.data["new_expiry_date"], "new_expiry_date")
                if call.data.get("new_expiry_date")
                else None
            )
            return {
                "item": decorate(
                    await get_manager(hass).async_renew(call.data["item_id"], new_date)
                )
            }
        except (ItemNotFoundError, ValueError) as err:
            _error(err)

    async def close(call: ServiceCall) -> dict[str, Any]:
        try:
            return {
                "item": decorate(
                    await get_manager(hass).async_close(
                        call.data["item_id"], call.data.get("reason")
                    )
                )
            }
        except (ItemNotFoundError, ValueError) as err:
            _error(err)

    async def reopen(call: ServiceCall) -> dict[str, Any]:
        try:
            return {"item": decorate(await get_manager(hass).async_reopen(call.data["item_id"]))}
        except ItemNotFoundError as err:
            _error(err)

    async def acknowledge(call: ServiceCall) -> dict[str, Any]:
        try:
            return {
                "item": decorate(
                    await get_manager(hass).async_acknowledge(
                        call.data["item_id"], call.data["acknowledged"]
                    )
                )
            }
        except (ItemNotFoundError, ValueError) as err:
            _error(err)

    async def search(call: ServiceCall) -> dict[str, Any]:
        rows = get_manager(hass).search(call.data["query"], limit=call.data["limit"])
        return {"items": [decorate(item) for item in rows], "count": len(rows)}

    hass.services.async_register(
        DOMAIN,
        "create_item",
        create,
        schema=vol.Schema(CREATE_FIELDS),
        supports_response=SupportsResponse.OPTIONAL,
    )
    update_schema: dict[Any, Any] = {vol.Required("item_id"): cv.string, **UPDATE_FIELDS}
    hass.services.async_register(
        DOMAIN,
        "update_item",
        update,
        schema=vol.Schema(update_schema),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        "delete_item",
        delete,
        schema=vol.Schema({vol.Required("item_id"): cv.string}),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        "renew_item",
        renew,
        schema=vol.Schema(
            {vol.Required("item_id"): cv.string, vol.Optional("new_expiry_date"): cv.string}
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        "close_item",
        close,
        schema=vol.Schema({vol.Required("item_id"): cv.string, vol.Optional("reason"): cv.string}),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        "reopen_item",
        reopen,
        schema=vol.Schema({vol.Required("item_id"): cv.string}),
        supports_response=SupportsResponse.OPTIONAL,
    )
    ack_schema = vol.Schema(
        {vol.Required("item_id"): cv.string, vol.Optional("acknowledged", default=True): cv.boolean}
    )
    hass.services.async_register(
        DOMAIN,
        "acknowledge_item",
        acknowledge,
        schema=ack_schema,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        "reset_acknowledgement",
        acknowledge,
        schema=vol.Schema(
            {
                vol.Required("item_id"): cv.string,
                vol.Optional("acknowledged", default=False): cv.boolean,
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        "search_items",
        search,
        schema=vol.Schema(
            {
                vol.Required("query"): cv.string,
                vol.Optional("limit", default=25): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=500)
                ),
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )
    common = {
        vol.Optional("category"): cv.string,
        vol.Optional("important_only", default=False): cv.boolean,
        vol.Optional("limit", default=100): vol.All(vol.Coerce(int), vol.Range(min=1, max=500)),
    }
    between_schema: dict[Any, Any] = {
        vol.Required("start"): cv.string,
        vol.Required("end"): cv.string,
    }
    between_schema.update(common)
    hass.services.async_register(
        DOMAIN,
        "get_upcoming",
        lambda call: _query(call),
        schema=vol.Schema(
            {
                vol.Optional("days", default=180): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=36500)
                ),
                **common,
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "get_actionable",
        lambda call: _query(call, actionable_only=True),
        schema=vol.Schema(common),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "get_urgent",
        lambda call: _query(call, urgent_only=True),
        schema=vol.Schema(common),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "get_expired",
        lambda call: _query(call, expired_only=True),
        schema=vol.Schema(common),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "get_between",
        lambda call: _query(call),
        schema=vol.Schema(between_schema),
        supports_response=SupportsResponse.ONLY,
    )


def async_unregister_services(hass: HomeAssistant) -> None:
    for service in (*MUTATIONS, *QUERIES):
        hass.services.async_remove(DOMAIN, service)
