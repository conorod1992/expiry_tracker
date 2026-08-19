from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.expiry_tracker.const import DOMAIN
from custom_components.expiry_tracker.manager import ExpiryTrackerManager
from custom_components.expiry_tracker.websocket_api import async_register_websocket_commands

from .conftest import MemoryStorage


async def setup(hass, hass_ws_client, token=None):
    manager = ExpiryTrackerManager(MemoryStorage(), lambda: None)
    await manager.async_load()
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
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
