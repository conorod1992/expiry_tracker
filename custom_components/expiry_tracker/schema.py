"""Shared service and WebSocket field schemas."""

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

_ACTION_TYPES = [
    "renew",
    "replace",
    "review",
    "retest",
    "reregister",
    "cancel",
    "check",
    "custom",
]

CREATE_FIELDS = {
    vol.Required("name"): cv.string,
    vol.Required("expiry_date"): cv.string,
    vol.Optional("aliases", default=[]): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional("category", default="Other"): cv.string,
    vol.Optional("notes"): vol.Any(None, cv.string),
    vol.Optional("enabled", default=True): cv.boolean,
    vol.Optional("important", default=False): cv.boolean,
    vol.Optional("expose_entity", default=False): cv.boolean,
    vol.Optional("requires_action", default=True): cv.boolean,
    vol.Optional("action_type", default="renew"): vol.In(_ACTION_TYPES),
    vol.Optional("custom_action_label"): vol.Any(None, cv.string),
    vol.Optional("actionable_mode", default="offset"): vol.In(["immediate", "offset", "date"]),
    vol.Optional("actionable_offset_value", default=30): vol.All(
        vol.Coerce(int), vol.Range(min=0, max=36500)
    ),
    vol.Optional("actionable_offset_unit", default="days"): vol.In(["days", "months"]),
    vol.Optional("actionable_from"): vol.Any(None, cv.string),
    vol.Optional("warning_thresholds", default=[180, 90, 30, 7, 1]): vol.All(
        cv.ensure_list, [vol.All(vol.Coerce(int), vol.Range(min=0, max=36500))]
    ),
    vol.Optional("urgent_days_before", default=7): vol.All(
        vol.Coerce(int), vol.Range(min=0, max=36500)
    ),
    vol.Optional("notify_actionable", default=True): cv.boolean,
    vol.Optional("notify_urgent", default=True): cv.boolean,
    vol.Optional("notify_expiry", default=True): cv.boolean,
    vol.Optional("require_acknowledgement", default=False): cv.boolean,
    vol.Optional("repeat_until_acknowledged", default=False): cv.boolean,
    vol.Optional("repeat_interval_hours", default=24): vol.All(
        vol.Coerce(int), vol.Range(min=1, max=8760)
    ),
    vol.Optional("recurrence_months"): vol.Any(
        None, vol.All(vol.Coerce(int), vol.Range(min=1, max=1200))
    ),
}
UPDATE_FIELDS = {vol.Optional(str(key.schema)): value for key, value in CREATE_FIELDS.items()}
