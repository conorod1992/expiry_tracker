"""Validated immutable Expiry Tracker model."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

from .const import MAX_HISTORY


class ItemValidationError(ValueError):
    """Raised for invalid item input."""


class ItemNotFoundError(KeyError):
    """Raised when a stable item ID is unknown."""


class DuplicateItemIdError(ItemValidationError):
    """Raised for duplicate IDs."""


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _text(value: Any, field: str, *, required: bool = False) -> str | None:
    if value is None:
        if required:
            raise ItemValidationError(f"{field} is required")
        return None
    if not isinstance(value, str):
        raise ItemValidationError(f"{field} must be a string")
    result = " ".join(value.split())
    if required and not result:
        raise ItemValidationError(f"{field} must not be empty")
    if len(result) > (120 if field in {"name", "category"} else 4000):
        raise ItemValidationError(f"{field} is too long")
    return result or None


def _date(value: Any, field: str, *, optional: bool = False) -> date | None:
    if value is None and optional:
        return None
    try:
        return (
            date.fromisoformat(value)
            if isinstance(value, str)
            else value
            if isinstance(value, date)
            else date.fromisoformat("")
        )
    except ValueError as err:
        raise ItemValidationError(f"{field} must be an ISO date (YYYY-MM-DD)") from err


def _positive_int(value: Any, field: str, *, minimum: int = 0, maximum: int = 36500) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ItemValidationError(f"{field} must be an integer from {minimum} to {maximum}")
    return int(value)


def _aliases(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)) or isinstance(value, str):
        raise ItemValidationError("aliases must be a list")
    result: list[str] = []
    for raw in value:
        alias = _text(raw, "alias", required=True)
        assert alias is not None
        if alias.casefold() not in {existing.casefold() for existing in result}:
            result.append(alias)
    return tuple(result)


def _history(value: Any) -> tuple[dict[str, Any], ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)) or not all(isinstance(row, dict) for row in value):
        raise ItemValidationError("history must be a list of objects")
    return tuple(dict(row) for row in value[-MAX_HISTORY:])


@dataclass(frozen=True, slots=True)
class ExpiryItem:
    id: str
    name: str
    expiry_date: date
    category: str = "Other"
    aliases: tuple[str, ...] = ()
    notes: str | None = None
    enabled: bool = True
    important: bool = False
    expose_entity: bool = False
    requires_action: bool = True
    actionable_mode: str = "offset"
    actionable_offset_value: int = 30
    actionable_offset_unit: str = "days"
    actionable_from: date | None = None
    warning_thresholds: tuple[int, ...] = (180, 90, 30, 7, 1)
    urgent_days_before: int = 7
    notify_actionable: bool = True
    notify_urgent: bool = True
    notify_expiry: bool = True
    require_acknowledgement: bool = False
    repeat_until_acknowledged: bool = False
    repeat_interval_hours: int = 24
    acknowledged: bool = False
    acknowledged_stage: str | None = None
    acknowledged_at: str | None = None
    recurrence_months: int | None = None
    closed: bool = False
    closed_at: str | None = None
    closed_reason: str | None = None
    last_notifications: dict[str, str] | None = None
    history: tuple[dict[str, Any], ...] = ()
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def create(cls, data: Mapping[str, Any]) -> ExpiryItem:
        now = utc_now_iso()
        return cls.from_dict({"id": str(uuid4()), "created_at": now, "updated_at": now, **data})

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ExpiryItem:
        try:
            item_id = str(UUID(str(data.get("id"))))
        except (ValueError, TypeError, AttributeError) as err:
            raise ItemValidationError("id must be a UUID") from err
        name = _text(data.get("name"), "name", required=True)
        expiry = _date(data.get("expiry_date"), "expiry_date")
        assert name is not None and expiry is not None
        category = _text(data.get("category", "Other"), "category", required=True)
        assert category is not None
        mode = data.get("actionable_mode", "offset")
        if mode not in {"immediate", "offset", "date"}:
            raise ItemValidationError("actionable_mode must be immediate, offset, or date")
        unit = data.get("actionable_offset_unit", "days")
        if unit not in {"days", "months"}:
            raise ItemValidationError("actionable_offset_unit must be days or months")
        actionable_from = _date(data.get("actionable_from"), "actionable_from", optional=True)
        if mode == "date" and actionable_from is None:
            raise ItemValidationError("actionable_from is required for specific date mode")
        if actionable_from is not None and actionable_from > expiry:
            raise ItemValidationError("actionable_from cannot be after expiry_date")
        raw_thresholds = data.get("warning_thresholds", [180, 90, 30, 7, 1])
        if not isinstance(raw_thresholds, (list, tuple)):
            raise ItemValidationError("warning_thresholds must be a list")
        thresholds = tuple(
            sorted({_positive_int(v, "warning threshold") for v in raw_thresholds}, reverse=True)
        )
        bools: dict[str, bool] = {}
        for field, default in (
            ("enabled", True),
            ("important", False),
            ("expose_entity", False),
            ("requires_action", True),
            ("notify_actionable", True),
            ("notify_urgent", True),
            ("notify_expiry", True),
            ("require_acknowledgement", False),
            ("repeat_until_acknowledged", False),
            ("acknowledged", False),
            ("closed", False),
        ):
            value = data.get(field, default)
            if not isinstance(value, bool):
                raise ItemValidationError(f"{field} must be a boolean")
            bools[field] = value
        recurrence = data.get("recurrence_months")
        if recurrence is not None:
            recurrence = _positive_int(recurrence, "recurrence_months", minimum=1, maximum=1200)
        acknowledged_stage = data.get("acknowledged_stage")
        if acknowledged_stage not in {None, "actionable", "urgent", "expiry"}:
            raise ItemValidationError(
                "acknowledged_stage must be actionable, urgent, expiry, or null"
            )
        last = data.get("last_notifications", {})
        if not isinstance(last, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in last.items()
        ):
            raise ItemValidationError("last_notifications must be a string map")
        created = str(data.get("created_at") or utc_now_iso())
        updated = str(data.get("updated_at") or created)
        closed_at = _text(data.get("closed_at"), "closed_at")
        closed_reason = _text(data.get("closed_reason"), "closed_reason")
        if bools["closed"] and closed_at is None:
            closed_at = updated
        if not bools["closed"]:
            closed_at = None
            closed_reason = None
        return cls(
            id=item_id,
            name=name,
            expiry_date=expiry,
            category=category,
            aliases=_aliases(data.get("aliases")),
            notes=_text(data.get("notes"), "notes"),
            actionable_mode=mode,
            actionable_offset_value=_positive_int(
                data.get("actionable_offset_value", 30), "actionable_offset_value"
            ),
            actionable_offset_unit=unit,
            actionable_from=actionable_from,
            warning_thresholds=thresholds,
            urgent_days_before=_positive_int(
                data.get("urgent_days_before", 7), "urgent_days_before"
            ),
            repeat_interval_hours=_positive_int(
                data.get("repeat_interval_hours", 24),
                "repeat_interval_hours",
                minimum=1,
                maximum=8760,
            ),
            acknowledged_at=_text(data.get("acknowledged_at"), "acknowledged_at"),
            acknowledged_stage=acknowledged_stage,
            recurrence_months=recurrence,
            closed_at=closed_at,
            closed_reason=closed_reason,
            last_notifications=dict(last),
            history=_history(data.get("history")),
            created_at=created,
            updated_at=updated,
            **bools,
        )

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["expiry_date"] = self.expiry_date.isoformat()
        result["actionable_from"] = (
            self.actionable_from.isoformat() if self.actionable_from else None
        )
        result["aliases"] = list(self.aliases)
        result["warning_thresholds"] = list(self.warning_thresholds)
        result["history"] = [dict(row) for row in self.history]
        return result

    def updated(self, changes: Mapping[str, Any]) -> ExpiryItem:
        forbidden = {
            "id",
            "created_at",
            "history",
            "last_notifications",
            "acknowledged",
            "acknowledged_stage",
            "acknowledged_at",
            "closed",
            "closed_at",
            "closed_reason",
        } & changes.keys()
        if forbidden:
            raise ItemValidationError(
                f"fields cannot be updated directly: {', '.join(sorted(forbidden))}"
            )
        return self.from_dict({**self.to_dict(), **changes, "updated_at": utc_now_iso()})
