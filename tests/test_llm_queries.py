from datetime import date

from custom_components.expiry_tracker.llm import _matches_search, _view_items
from custom_components.expiry_tracker.models import ExpiryItem

from .conftest import item_data


def _item(name: str, expiry_date: str, **changes):
    return ExpiryItem.create(item_data(name=name, expiry_date=expiry_date, **changes))


def test_next_expiry_returns_upcoming_active_items_in_date_order():
    today = date(2026, 8, 28)
    items = [
        _item("Later", "2026-10-01"),
        _item("Next", "2026-09-01"),
        _item("Expired", "2026-08-20"),
        _item("Disabled", "2026-08-29", enabled=False),
        _item("Closed", "2026-08-30", closed=True),
    ]

    result = _view_items(items, today, "next_expiry")

    assert [row["name"] for row in result] == ["Next", "Later"]


def test_next_actionable_prioritizes_ready_work_then_future_action_date():
    today = date(2026, 8, 28)
    items = [
        _item(
            "Future first",
            "2026-10-01",
            actionable_mode="date",
            actionable_from="2026-09-05",
        ),
        _item(
            "Ready later expiry",
            "2026-09-20",
            actionable_mode="immediate",
        ),
        _item(
            "Ready sooner expiry",
            "2026-09-10",
            actionable_mode="immediate",
        ),
        _item(
            "Passive",
            "2026-09-01",
            requires_action=False,
            actionable_mode="immediate",
        ),
    ]

    result = _view_items(items, today, "next_actionable")

    assert [row["name"] for row in result] == [
        "Ready sooner expiry",
        "Ready later expiry",
        "Future first",
    ]


def test_recently_completed_uses_history_and_includes_completed_cancellation():
    today = date(2026, 8, 28)
    renewed = _item(
        "Renewed",
        "2027-08-28",
        history=[{"type": "renewed", "at": "2026-08-27T12:00:00Z"}],
    )
    cancelled = _item(
        "Cancelled",
        "2026-08-30",
        action_type="cancel",
        closed=True,
        closed_reason="Marked as cancelled",
        history=[
            {
                "type": "closed",
                "at": "2026-08-26T12:00:00Z",
                "reason": "Marked as cancelled",
            }
        ],
    )
    stale = _item(
        "Old completion",
        "2027-01-01",
        history=[{"type": "renewed", "at": "2026-01-01T12:00:00Z"}],
    )

    result = _view_items([cancelled, stale, renewed], today, "recently_completed", recent_days=30)

    assert [row["name"] for row in result] == ["Renewed", "Cancelled"]
    assert result[0]["last_completed_at"] == "2026-08-27T12:00:00Z"


def test_historical_search_matching_includes_closed_items_and_aliases():
    cancelled = _item(
        "Driving licence",
        "2026-08-30",
        aliases=["licence renewal"],
        closed=True,
        closed_reason="Marked as cancelled",
    )

    assert _matches_search(cancelled, "driving")
    assert _matches_search(cancelled, "renewal")
    assert not _matches_search(cancelled, "passport")


def test_expiring_this_year_includes_past_and_future_dates_but_not_closed_items():
    today = date(2026, 8, 28)
    items = [
        _item("Earlier this year", "2026-02-01"),
        _item("Later this year", "2026-12-01"),
        _item("Next year", "2027-01-01"),
        _item("Closed this year", "2026-11-01", closed=True),
    ]

    result = _view_items(items, today, "expiring_this_year")

    assert [row["name"] for row in result] == ["Earlier this year", "Later this year"]


def test_dismissed_outstanding_only_returns_actionable_dismissed_work():
    today = date(2026, 8, 28)
    items = [
        _item(
            "Dismissed",
            "2026-09-10",
            actionable_mode="immediate",
            acknowledged=True,
            acknowledged_stage="actionable",
        ),
        _item("Needs attention", "2026-09-10", actionable_mode="immediate"),
        _item(
            "Future dismissed flag",
            "2026-12-01",
            actionable_mode="date",
            actionable_from="2026-11-01",
            acknowledged=True,
            acknowledged_stage="actionable",
        ),
    ]

    result = _view_items(items, today, "dismissed_outstanding")

    assert [row["name"] for row in result] == ["Dismissed"]
