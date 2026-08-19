"""Single-entry configuration and collection-wide options."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_DEFAULT_URGENT_DAYS,
    CONF_DEFAULT_WARNING_THRESHOLDS,
    CONF_NOTIFICATION_SERVICE,
    CONF_NOTIFICATION_TARGET,
    CONF_SHOW_PANEL,
    DEFAULT_NOTIFICATION_SERVICE,
    DEFAULT_SHOW_PANEL,
    DEFAULT_URGENT_DAYS,
    DEFAULT_WARNING_THRESHOLDS,
    DOMAIN,
    NAME,
)


class ExpiryTrackerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    MINOR_VERSION = 0

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return self.async_create_entry(title=NAME, data={})
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ExpiryTrackerOptionsFlow:
        return ExpiryTrackerOptionsFlow()


class ExpiryTrackerOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SHOW_PANEL, default=options.get(CONF_SHOW_PANEL, DEFAULT_SHOW_PANEL)
                    ): bool,
                    vol.Required(
                        CONF_DEFAULT_WARNING_THRESHOLDS,
                        default=options.get(
                            CONF_DEFAULT_WARNING_THRESHOLDS, DEFAULT_WARNING_THRESHOLDS
                        ),
                    ): vol.All(
                        cv.ensure_list,
                        [vol.All(vol.Coerce(int), vol.Range(min=0, max=36500))],
                    ),
                    vol.Required(
                        CONF_DEFAULT_URGENT_DAYS,
                        default=options.get(CONF_DEFAULT_URGENT_DAYS, DEFAULT_URGENT_DAYS),
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=36500)),
                    vol.Optional(
                        CONF_NOTIFICATION_SERVICE,
                        default=options.get(
                            CONF_NOTIFICATION_SERVICE, DEFAULT_NOTIFICATION_SERVICE
                        ),
                    ): str,
                    vol.Optional(
                        CONF_NOTIFICATION_TARGET, default=options.get(CONF_NOTIFICATION_TARGET, "")
                    ): str,
                }
            ),
        )
