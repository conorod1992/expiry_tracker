"""Pure date and status calculations."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from .models import ExpiryItem


class ExpiryStatus(StrEnum):
    """Mutually exclusive derived status, highest precedence last in evaluation."""

    VALID = "valid"
    WARNING = "warning"
    ACTIONABLE = "actionable"
    URGENT = "urgent"
    EXPIRED = "expired"


class AttentionStage(StrEnum):
    """Milestone-specific stages which can be acknowledged independently."""

    ACTIONABLE = "actionable"
    URGENT = "urgent"
    EXPIRY = "expiry"


def subtract_months(value: date, months: int) -> date:
    """Subtract calendar months, clamping to the destination month's last day."""
    absolute = value.year * 12 + value.month - 1 - months
    year, month_index = divmod(absolute, 12)
    if not 1 <= year <= 9999:
        return date.min
    month = month_index + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def add_months(value: date, months: int) -> date:
    """Add calendar months, clamping leap/month-end dates deterministically."""
    absolute = value.year * 12 + value.month - 1 + months
    year, month_index = divmod(absolute, 12)
    if not 1 <= year <= 9999:
        raise ValueError("recurrence produces an out-of-range date")
    month = month_index + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


@dataclass(frozen=True, slots=True)
class ExpiryState:
    """Calculated dates and current state for one item."""

    status: ExpiryStatus
    days_until_expiry: int
    actionable_date: date
    warning_date: date | None
    urgent_date: date
    actionable: bool
    attention_stage: AttentionStage | None
    acknowledged: bool
    requires_attention: bool
    renewal_outstanding: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "days_until_expiry": self.days_until_expiry,
            "actionable_date": self.actionable_date.isoformat(),
            "warning_date": self.warning_date.isoformat() if self.warning_date else None,
            "urgent_date": self.urgent_date.isoformat(),
            "actionable": self.actionable,
            "attention_stage": self.attention_stage.value if self.attention_stage else None,
            "acknowledged": self.acknowledged,
            "requires_attention": self.requires_attention,
            "renewal_outstanding": self.renewal_outstanding,
        }


def calculate_state(item: ExpiryItem, today: date) -> ExpiryState:
    """Calculate non-overlapping status with expired > urgent > actionable > warning."""
    expiry = item.expiry_date
    if item.actionable_mode == "immediate":
        actionable_date = date.min
    elif item.actionable_mode == "date":
        assert item.actionable_from is not None
        actionable_date = item.actionable_from
    elif item.actionable_offset_unit == "months":
        actionable_date = subtract_months(expiry, item.actionable_offset_value)
    else:
        actionable_date = expiry - timedelta(days=item.actionable_offset_value)
    thresholds = item.warning_thresholds
    warning_date = expiry - timedelta(days=max(thresholds)) if thresholds else None
    urgent_date = expiry - timedelta(days=item.urgent_days_before)
    if today > expiry:
        status = ExpiryStatus.EXPIRED
    elif item.requires_action and today >= urgent_date:
        status = ExpiryStatus.URGENT
    elif item.requires_action and today >= actionable_date:
        status = ExpiryStatus.ACTIONABLE
    elif warning_date is not None and today >= warning_date:
        status = ExpiryStatus.WARNING
    else:
        status = ExpiryStatus.VALID
    actionable = bool(item.requires_action and today >= actionable_date)
    attention_stage = (
        AttentionStage.EXPIRY
        if item.requires_action and today >= expiry
        else AttentionStage.URGENT
        if item.requires_action and today >= urgent_date
        else AttentionStage.ACTIONABLE
        if actionable
        else None
    )
    acknowledged = bool(
        attention_stage
        and (
            item.acknowledged_stage == attention_stage.value
            or (item.acknowledged and item.acknowledged_stage is None)
        )
    )
    requires_attention = bool(
        item.enabled and not item.closed and item.requires_action and attention_stage and not acknowledged
    )
    renewal_outstanding = bool(
        item.enabled and not item.closed and item.requires_action and today > expiry
    )
    return ExpiryState(
        status=status,
        days_until_expiry=(expiry - today).days,
        actionable_date=actionable_date,
        warning_date=warning_date,
        urgent_date=urgent_date,
        actionable=actionable,
        attention_stage=attention_stage,
        acknowledged=acknowledged,
        requires_attention=requires_attention,
        renewal_outstanding=renewal_outstanding,
    )
