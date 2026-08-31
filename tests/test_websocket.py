from uuid import uuid4

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.expiry_tracker.const import (
    CONF_DEFAULT_URGENT_DAYS,
    CONF_DEFAULT_WARNING_THRESHOLDS,
    CONF_USE_REMINDERS,
    DOMAIN,
)
from custom_components.expiry_tracker.manager import ExpiryTrackerManager
from custom_components.expiry_tracker.websocket_api import async_register_websocket_commands

from .conftest import MemoryStorage, item_data


async def setup(hass, hass_ws_client, token=None, *, options=None, records=None):
    manager = ExpiryTrackerManager(MemoryStorage(records), lambda: None)
    await manager.async_load()
    entry = MockConfigEntry(domain=DOMAIN, data={}, options=options or {})
    entry.runtime_data = manager
    entry.add_to_hass(hass)
    client = await hass_ws_client(hass, token) if token else await hass_ws_client(hass)
    async_register_websocket_commands(hass)
    return client


async def test_admin_crud_renew_ack_and_filters(hass, hass_ws_client):
    client = await setup(hass, hass_ws_client)
    await client.send_json_auto_id(
        {
            "type": "expiry_tracker/create",
            "name": "Passport",
            "expiry_date": "2027-08-19",
            "aliases": ["travel document"],
            "actionable_mode": "immediate",
        }
    )
    created = await client.receive_json()
    assert created["success"]
    item_id = created["result"]["id"]
    await client.send_json_auto_id(
        {"type": "expiry_tracker/list", "search": "travel", "actionable_only": True}
    )
    assert (await client.receive_json())["result"]["items"][0]["id"] == item_id
    await client.send_json_auto_id({"type": "expiry_tracker/acknowledge", "item_id": item_id})
    assert (await client.receive_json())["result"]["acknowledged"]
    await client.send_json_auto_id(
        {"type": "expiry_tracker/renew", "item_id": item_id, "new_expiry_date": "2037-08-19"}
    )
    assert (await client.receive_json())["result"]["expiry_date"] == "2037-08-19"


async def test_create_uses_configured_collection_defaults_when_omitted(hass, hass_ws_client):
    client = await setup(
        hass,
        hass_ws_client,
        options={
            CONF_DEFAULT_WARNING_THRESHOLDS: [45, 10],
            CONF_DEFAULT_URGENT_DAYS: 4,
        },
    )
    await client.send_json_auto_id(
        {
            "type": "expiry_tracker/create",
            "name": "Passport",
            "expiry_date": "2027-08-19",
        }
    )
    created = await client.receive_json()
    assert created["success"]
    assert created["result"]["warning_thresholds"] == [45, 10]
    assert created["result"]["urgent_days_before"] == 4


async def test_search_filters_before_limit_and_can_include_closed(hass, hass_ws_client):
    records = [
        {
            **item_data(name=f"Item {index:03d}", category="Other"),
            "id": str(uuid4()),
        }
        for index in range(500)
    ]
    target_id = str(uuid4())
    records.append(
        {
            **item_data(name="Item ZZZ", category="Target", closed=True),
            "id": target_id,
        }
    )
    client = await setup(hass, hass_ws_client, records=records)

    await client.send_json_auto_id(
        {
            "type": "expiry_tracker/list",
            "search": "item",
            "category": "Target",
            "closed": True,
        }
    )
    result = await client.receive_json()
    assert result["success"]
    assert result["result"]["pagination"]["total"] == 1
    assert [item["id"] for item in result["result"]["items"]] == [target_id]


async def test_non_admin_reads_but_cannot_mutate(hass, hass_ws_client, hass_read_only_access_token):
    await setup(hass, hass_ws_client)
    client = await hass_ws_client(hass, hass_read_only_access_token)
    await client.send_json_auto_id({"type": "expiry_tracker/list"})
    assert (await client.receive_json())["success"]
    await client.send_json_auto_id(
        {"type": "expiry_tracker/create", "name": "No", "expiry_date": "2027-01-01"}
    )
    denied = await client.receive_json()
    assert not denied["success"] and denied["error"]["code"] == "unauthorized"


async def test_settings_reports_native_delivery_when_reminders_are_inactive(hass, hass_ws_client):
    client = await setup(hass, hass_ws_client)
    await client.send_json_auto_id({"type": "expiry_tracker/settings"})
    result = await client.receive_json()
    assert result["success"]
    assert result["result"]["capabilities"]["delivery_backend"] == "native"
    assert not result["result"]["capabilities"]["reminders_available"]


async def test_settings_reports_reminders_as_the_active_delivery_backend(hass, hass_ws_client):
    client = await setup(hass, hass_ws_client)
    hass.data["expiry_tracker_reminders_active"] = True
    await client.send_json_auto_id({"type": "expiry_tracker/settings"})
    result = await client.receive_json()
    assert result["success"]
    assert result["result"]["capabilities"]["delivery_backend"] == "reminders"


async def test_settings_and_delivery_update_use_existing_reminders_option(hass, hass_ws_client):
    client = await setup(hass, hass_ws_client)
    for service in ("create", "list", "update", "delete", "external_action"):
        hass.services.async_register("reminders", service, lambda call: None)
    await client.send_json_auto_id({"type": "expiry_tracker/settings"})
    available = await client.receive_json()
    assert available["result"]["capabilities"]["reminders_available"]
    await client.send_json_auto_id(
        {"type": "expiry_tracker/update_delivery", CONF_USE_REMINDERS: True}
    )
    updated = await client.receive_json()
    assert updated["success"]
    assert updated["result"]["options"][CONF_USE_REMINDERS] is True
    assert updated["result"]["updated"] is True
    assert "capabilities" not in updated["result"]
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.options == {CONF_USE_REMINDERS: True}
