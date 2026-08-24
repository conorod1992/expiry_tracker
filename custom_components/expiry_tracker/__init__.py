"""Expiry Tracker integration setup."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig  # type: ignore[attr-defined]
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_SHOW_PANEL,
    DEFAULT_SHOW_PANEL,
    DOMAIN,
    PANEL_ELEMENT,
    PANEL_STATIC_URL,
    PANEL_URL,
    PLATFORMS,
    SIGNAL_UPDATED,
    VERSION,
)
from .helpers import local_date
from .manager import ExpiryTrackerManager
from .notifications import async_setup_notifications
from .reminders import async_setup_reminders
from .services import async_register_services, async_unregister_services
from .storage import ExpiryTrackerStorage
from .websocket_api import async_register_websocket_commands

type ExpiryTrackerConfigEntry = ConfigEntry[ExpiryTrackerManager]
_FRONTEND = f"{DOMAIN}_frontend_registered"
_WEBSOCKET = f"{DOMAIN}_websocket_registered"


async def async_setup_entry(hass: HomeAssistant, entry: ExpiryTrackerConfigEntry) -> bool:
    manager = ExpiryTrackerManager(
        ExpiryTrackerStorage(hass),
        lambda: async_dispatcher_send(hass, SIGNAL_UPDATED),
        local_date,
    )
    try:
        await manager.async_load()
    except Exception as err:
        raise ConfigEntryError(
            "Expiry Tracker storage could not be loaded; stored data was not changed"
        ) from err
    entry.runtime_data = manager
    entry.async_on_unload(entry.add_update_listener(_options_updated))
    if not hass.data.get(_WEBSOCKET):
        async_register_websocket_commands(hass)
        hass.data[_WEBSOCKET] = True
    await async_register_services(hass)
    if unsubscribe := await async_setup_reminders(hass, entry, manager):
        entry.async_on_unload(unsubscribe)
    entry.async_on_unload(async_setup_notifications(hass, entry))
    await _setup_frontend(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ExpiryTrackerConfigEntry) -> bool:
    result = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    frontend.async_remove_panel(hass, PANEL_URL, warn_if_unknown=False)
    async_unregister_services(hass)
    hass.data["expiry_tracker_reminders_active"] = False
    return result


async def _options_updated(hass: HomeAssistant, entry: ExpiryTrackerConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def _setup_frontend(hass: HomeAssistant, entry: ExpiryTrackerConfigEntry) -> None:
    if not hass.data.get(_FRONTEND):
        path = Path(__file__).parent / "frontend"
        await hass.http.async_register_static_paths(
            [StaticPathConfig(PANEL_STATIC_URL, str(path), True)]
        )
        hass.data[_FRONTEND] = True
    frontend.async_remove_panel(hass, PANEL_URL, warn_if_unknown=False)
    if entry.options.get(CONF_SHOW_PANEL, DEFAULT_SHOW_PANEL):
        await panel_custom.async_register_panel(
            hass,
            frontend_url_path=PANEL_URL,
            webcomponent_name=PANEL_ELEMENT,
            sidebar_title="Expiry Tracker",
            sidebar_icon="mdi:calendar-alert",
            module_url=f"{PANEL_STATIC_URL}/expiry-tracker-panel.js?v={VERSION}",
            require_admin=False,
            config_panel_domain=DOMAIN,
        )
