"""Constants for Expiry Tracker."""

from typing import Final

DOMAIN: Final = "expiry_tracker"
NAME: Final = "Expiry Tracker"
VERSION: Final = "1.0.0"
PLATFORMS: Final = ["sensor", "calendar"]
STORAGE_KEY: Final = "expiry_tracker.items"
STORAGE_VERSION: Final = 2
STORAGE_MINOR_VERSION: Final = 0
SIGNAL_UPDATED: Final = "expiry_tracker_updated"

CONF_SHOW_PANEL: Final = "show_panel"
CONF_DEFAULT_WARNING_THRESHOLDS: Final = "default_warning_thresholds"
CONF_DEFAULT_URGENT_DAYS: Final = "default_urgent_days"
CONF_NOTIFICATION_SERVICE: Final = "notification_service"
CONF_NOTIFICATION_TARGET: Final = "notification_target"
CONF_USE_REMINDERS: Final = "use_reminders"
DEFAULT_SHOW_PANEL: Final = True
DEFAULT_WARNING_THRESHOLDS: Final = [180, 90, 30, 7, 1]
DEFAULT_URGENT_DAYS: Final = 7
DEFAULT_NOTIFICATION_SERVICE: Final = ""
DEFAULT_USE_REMINDERS: Final = False

REMINDERS_DOMAIN: Final = "reminders"
REMINDERS_SOURCE: Final = "expiry_tracker"
REMINDERS_LIFECYCLE_EVENT: Final = "reminders_lifecycle"
RENEWAL_REQUESTED_EVENT: Final = "expiry_tracker_renewal_requested"

PANEL_URL: Final = "expiry-tracker"
PANEL_ELEMENT: Final = "expiry-tracker-panel"
PANEL_STATIC_URL: Final = "/expiry_tracker_static"
MAX_LIST_LIMIT: Final = 500
MAX_QUERY_LIMIT: Final = 500
MAX_HISTORY: Final = 50

BUILT_IN_CATEGORIES: Final = (
    "Identity/document",
    "Vehicle",
    "Insurance",
    "Medical",
    "Professional",
    "Pet",
    "Financial",
    "Home",
    "Subscription/service",
    "Warranty",
    "Other",
)
