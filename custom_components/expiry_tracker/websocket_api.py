"""Authenticated WebSocket API for the management panel."""
# mypy: disable-error-code="attr-defined,dict-item"

from __future__ import annotations

from datetime import date
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import ActiveConnection
from homeassistant.core import HomeAssistant, callback

from .const import BUILT_IN_CATEGORIES, CONF_USE_REMINDERS, MAX_LIST_LIMIT
from .helpers import creation_payload, decorate, get_entry, get_manager, local_today
from .models import ItemNotFoundError, ItemValidationError
from .reminders import reminders_available
from .schema import CREATE_FIELDS, UPDATE_FIELDS

_UPDATE_KEYS = {str(key.schema) for key in UPDATE_FIELDS}


def _send_error(connection: ActiveConnection, msg_id: int, err: Exception) -> None:
    code = "not_found" if isinstance(err, ItemNotFoundError) else "invalid_format"
    connection.send_error(msg_id, code, str(err))


@websocket_api.websocket_command(
    {
        "type": "expiry_tracker/list",
        vol.Optional("search"): str,
        vol.Optional("category"): str,
        vol.Optional("status"): str,
        vol.Optional("actionable_only", default=False): bool,
        vol.Optional("important_only", default=False): bool,
        vol.Optional("enabled"): bool,
        vol.Optional("closed", default=False): bool,
        vol.Optional("sort", default="expiry"): vol.In(["expiry", "name", "status", "actionable"]),
        vol.Optional("direction", default="asc"): vol.In(["asc", "desc"]),
        vol.Optional("offset", default=0): vol.All(int, vol.Range(min=0)),
        vol.Optional("limit", default=100): vol.All(int, vol.Range(min=1, max=MAX_LIST_LIMIT)),
    }
)
@callback
def websocket_list(hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]) -> None:
    today = local_today()
    manager = get_manager(hass)
    source = (
        manager.search(msg["search"], limit=None, include_closed=msg["closed"])
        if msg.get("search")
        else manager.list_items()
    )
    rows = [decorate(item, today) for item in source]
    rows = [
        row
        for row in rows
        if (msg.get("category") is None or row["category"] == msg["category"])
        and (msg.get("status") is None or row["status"] == msg["status"])
        and (not msg["actionable_only"] or row["requires_attention"])
        and (not msg["important_only"] or row["important"])
        and (msg.get("enabled") is None or row["enabled"] is msg["enabled"])
        and row["closed"] is msg["closed"]
    ]
    rank = {"expired": 0, "urgent": 1, "actionable": 2, "warning": 3, "valid": 4}
    keys = {
        "expiry": lambda row: (row["expiry_date"], row["name"].casefold()),
        "name": lambda row: (row["name"].casefold(), row["expiry_date"]),
        "status": lambda row: (rank[row["status"]], row["expiry_date"]),
        "actionable": lambda row: (row["actionable_date"], row["expiry_date"]),
    }
    rows.sort(key=keys[msg["sort"]], reverse=msg["direction"] == "desc")
    offset, limit = msg["offset"], msg["limit"]
    connection.send_result(
        msg["id"],
        {
            "items": rows[offset : offset + limit],
            "pagination": {
                "offset": offset,
                "limit": limit,
                "total": len(rows),
                "has_more": offset + limit < len(rows),
            },
        },
    )


@websocket_api.websocket_command({"type": "expiry_tracker/get", vol.Required("item_id"): str})
@callback
def websocket_get(hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]) -> None:
    try:
        connection.send_result(msg["id"], decorate(get_manager(hass).get_item(msg["item_id"])))
    except ItemNotFoundError as err:
        _send_error(connection, msg["id"], err)


@websocket_api.websocket_command({"type": "expiry_tracker/create", **CREATE_FIELDS})
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_create(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    try:
        data = {key: value for key, value in msg.items() if key not in {"id", "type"}}
        item = await get_manager(hass).async_create_item(creation_payload(hass, data))
        connection.send_result(msg["id"], decorate(item))
    except ItemValidationError as err:
        _send_error(connection, msg["id"], err)


@websocket_api.websocket_command(
    {"type": "expiry_tracker/update", vol.Required("item_id"): str, **UPDATE_FIELDS}
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_update(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    try:
        item = await get_manager(hass).async_update_item(
            msg["item_id"], {key: value for key, value in msg.items() if key in _UPDATE_KEYS}
        )
        connection.send_result(msg["id"], decorate(item))
    except (ItemValidationError, ItemNotFoundError) as err:
        _send_error(connection, msg["id"], err)


async def _workflow(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any], action: str
) -> None:
    try:
        manager = get_manager(hass)
        if action == "delete":
            item = await manager.async_delete_item(msg["item_id"])
            connection.send_result(msg["id"], {"deleted": True, "item_id": item.id})
        elif action == "renew":
            value = (
                date.fromisoformat(msg["new_expiry_date"]) if msg.get("new_expiry_date") else None
            )
            connection.send_result(
                msg["id"], decorate(await manager.async_renew(msg["item_id"], value))
            )
        elif action == "close":
            connection.send_result(
                msg["id"],
                decorate(await manager.async_close(msg["item_id"], msg.get("reason"))),
            )
        elif action == "reopen":
            connection.send_result(msg["id"], decorate(await manager.async_reopen(msg["item_id"])))
        else:
            connection.send_result(
                msg["id"],
                decorate(
                    await manager.async_acknowledge(
                        msg["item_id"], msg.get("acknowledged", True), msg.get("stage")
                    )
                ),
            )
    except (ItemNotFoundError, ItemValidationError, ValueError) as err:
        _send_error(connection, msg["id"], err)


@websocket_api.websocket_command({"type": "expiry_tracker/delete", vol.Required("item_id"): str})
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_delete(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    await _workflow(hass, connection, msg, "delete")


@websocket_api.websocket_command(
    {
        "type": "expiry_tracker/renew",
        vol.Required("item_id"): str,
        vol.Optional("new_expiry_date"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_renew(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    await _workflow(hass, connection, msg, "renew")


@websocket_api.websocket_command(
    {
        "type": "expiry_tracker/close",
        vol.Required("item_id"): str,
        vol.Optional("reason"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_close(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    await _workflow(hass, connection, msg, "close")


@websocket_api.websocket_command({"type": "expiry_tracker/reopen", vol.Required("item_id"): str})
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_reopen(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    await _workflow(hass, connection, msg, "reopen")


@websocket_api.websocket_command(
    {
        "type": "expiry_tracker/acknowledge",
        vol.Required("item_id"): str,
        vol.Optional("acknowledged", default=True): bool,
        vol.Optional("stage"): vol.In(["actionable", "urgent", "expiry"]),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_acknowledge(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    await _workflow(hass, connection, msg, "acknowledge")


@websocket_api.websocket_command({"type": "expiry_tracker/settings"})
@callback
def websocket_settings(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    connection.send_result(
        msg["id"],
        {
            "categories": list(BUILT_IN_CATEGORIES),
            "options": dict(get_entry(hass).options),
            "is_admin": bool(connection.user and connection.user.is_admin),
            "capabilities": {
                "llm_read": True,
                "llm_mutation": False,
                "reminders_available": reminders_available(hass),
                "reminders_active": bool(hass.data.get("expiry_tracker_reminders_active")),
                "delivery_backend": (
                    "reminders" if hass.data.get("expiry_tracker_reminders_active") else "native"
                ),
            },
        },
    )


@websocket_api.websocket_command(
    {"type": "expiry_tracker/update_delivery", vol.Required(CONF_USE_REMINDERS): bool}
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_update_delivery(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Update the existing delivery option and let its update listener reload us."""
    use_reminders = msg[CONF_USE_REMINDERS]
    if use_reminders and not reminders_available(hass):
        connection.send_error(msg["id"], "not_supported", "Reminders delivery is unavailable")
        return
    entry = get_entry(hass)
    options = {**entry.options, CONF_USE_REMINDERS: use_reminders}
    hass.config_entries.async_update_entry(entry, options=options)
    connection.send_result(
        msg["id"],
        {
            "options": options,
            "updated": True,
        },
    )


def async_register_websocket_commands(hass: HomeAssistant) -> None:
    for command in (
        websocket_list,
        websocket_get,
        websocket_create,
        websocket_update,
        websocket_delete,
        websocket_renew,
        websocket_close,
        websocket_reopen,
        websocket_acknowledge,
        websocket_settings,
        websocket_update_delivery,
    ):
        websocket_api.async_register_command(hass, command)
