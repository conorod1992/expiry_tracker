from homeassistant.components.diagnostics import REDACTED

from custom_components.expiry_tracker.const import (
    CONF_NOTIFICATION_SERVICE,
    CONF_NOTIFICATION_TARGET,
    CONF_SHOW_PANEL,
)
from custom_components.expiry_tracker.diagnostics import (
    _diagnostic_counts,
    _diagnostic_options,
)

from .conftest import item_data


def test_diagnostic_options_redact_notification_identifiers() -> None:
    options = {
        CONF_SHOW_PANEL: True,
        CONF_NOTIFICATION_SERVICE: "notify.mobile_app_personal_phone",
        CONF_NOTIFICATION_TARGET: "private-target-id",
    }

    result = _diagnostic_options(options)

    assert result[CONF_SHOW_PANEL] is True
    assert result[CONF_NOTIFICATION_SERVICE] == REDACTED
    assert result[CONF_NOTIFICATION_TARGET] == REDACTED
    assert "personal_phone" not in repr(result)
    assert "private-target-id" not in repr(result)


async def test_diagnostic_counts_hide_custom_category_names(manager) -> None:
    await manager.async_create_item(item_data(name="Policy", category="Insurance"))
    await manager.async_create_item(item_data(name="Private", category="Family private admin"))
    await manager.async_create_item(item_data(name="Private 2", category="Family private admin"))
    await manager.async_create_item(
        item_data(name="Other private", category="Confidential project")
    )

    result = _diagnostic_counts(manager)

    assert result["category_counts"] == {"Insurance": 1}
    assert result["custom_category_count"] == 2
    assert result["custom_category_item_count"] == 3
    assert "Family private admin" not in repr(result)
    assert "Confidential project" not in repr(result)
