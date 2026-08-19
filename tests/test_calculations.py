from datetime import date

import pytest

from custom_components.expiry_tracker.calculations import (
    ExpiryStatus,
    add_months,
    calculate_state,
    subtract_months,
)
from custom_components.expiry_tracker.models import ExpiryItem

from .conftest import item_data


@pytest.mark.parametrize(
    ("today", "status"),
    [
        (date(2027, 1, 1), ExpiryStatus.VALID),
        (date(2027, 3, 1), ExpiryStatus.WARNING),
        (date(2027, 7, 20), ExpiryStatus.ACTIONABLE),
        (date(2027, 8, 12), ExpiryStatus.URGENT),
        (date(2027, 8, 19), ExpiryStatus.URGENT),
        (date(2027, 8, 20), ExpiryStatus.EXPIRED),
    ],
)
def test_status_precedence(today, status):
    item = ExpiryItem.create(
        item_data(actionable_offset_value=30, warning_thresholds=[180], urgent_days_before=7)
    )
    assert calculate_state(item, today).status == status


def test_warning_does_not_imply_actionable():
    state = calculate_state(
        ExpiryItem.create(item_data(warning_thresholds=[365], actionable_offset_value=30)),
        date(2026, 9, 1),
    )
    assert state.status == "warning"
    assert state.actionable is False
    assert state.requires_attention is False


def test_actionability_modes_and_acknowledgement():
    immediate = ExpiryItem.create(item_data(actionable_mode="immediate", acknowledged=True))
    explicit = ExpiryItem.create(item_data(actionable_mode="date", actionable_from="2027-06-01"))
    assert calculate_state(immediate, date(2020, 1, 1)).actionable
    assert not calculate_state(immediate, date(2020, 1, 1)).requires_attention
    assert calculate_state(explicit, date(2027, 5, 31)).actionable is False
    assert calculate_state(explicit, date(2027, 6, 1)).actionable is True


def test_calendar_month_boundaries_and_leap_years():
    assert subtract_months(date(2025, 3, 31), 1) == date(2025, 2, 28)
    assert subtract_months(date(2024, 3, 31), 1) == date(2024, 2, 29)
    assert add_months(date(2024, 2, 29), 12) == date(2025, 2, 28)
    assert add_months(date(2024, 2, 29), 48) == date(2028, 2, 29)


def test_zero_day_thresholds():
    item = ExpiryItem.create(
        item_data(actionable_offset_value=0, urgent_days_before=0, warning_thresholds=[0])
    )
    state = calculate_state(item, item.expiry_date)
    assert state.status == "urgent"
    assert state.days_until_expiry == 0
