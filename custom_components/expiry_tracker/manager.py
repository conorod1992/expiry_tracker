"""Concurrency-safe collection manager and renewal workflow."""

from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Awaitable, Callable, Mapping
from contextlib import suppress
from datetime import UTC, date, datetime
from typing import Any, Protocol

from .calculations import AttentionStage, ExpiryState, add_months, calculate_state
from .const import MAX_HISTORY
from .models import DuplicateItemIdError, ExpiryItem, ItemNotFoundError, utc_now_iso


class StorageProtocol(Protocol):
    async def async_load(self) -> list[dict[str, Any]]: ...
    async def async_save(self, records: list[dict[str, Any]]) -> None: ...


def _system_local_date(value: datetime | None = None) -> date:
    """Fallback for standalone users of the manager outside Home Assistant."""
    return value.astimezone().date() if value is not None else datetime.now(UTC).astimezone().date()


class ExpiryTrackerManager:
    def __init__(
        self,
        storage: StorageProtocol,
        notify: Callable[[], None],
        local_date: Callable[[datetime | None], date] = _system_local_date,
    ) -> None:
        self._storage = storage
        self._notify = notify
        self._local_date = local_date
        self._items: dict[str, ExpiryItem] = {}
        self._lock = asyncio.Lock()
        self._change_listener: Callable[[str, ExpiryItem | None], Awaitable[None]] | None = None

    def set_change_listener(
        self, listener: Callable[[str, ExpiryItem | None], Awaitable[None]] | None
    ) -> None:
        """Set the optional external delivery reconciliation hook."""
        self._change_listener = listener

    async def _changed(self, action: str, item: ExpiryItem | None) -> None:
        if self._change_listener:
            await self._change_listener(action, item)

    async def async_load(self) -> None:
        records = await self._storage.async_load()
        loaded: dict[str, ExpiryItem] = {}
        migrated = False
        for record in records:
            item = ExpiryItem.from_dict(record)
            if item.acknowledged and item.acknowledged_stage is None:
                acknowledged_on = self._local_date(None)
                if item.acknowledged_at:
                    with suppress(ValueError):
                        acknowledged_on = self._local_date(
                            datetime.fromisoformat(item.acknowledged_at.replace("Z", "+00:00"))
                        )
                stage = calculate_state(item, acknowledged_on).attention_stage
                if stage:
                    item = ExpiryItem.from_dict(
                        {**item.to_dict(), "acknowledged_stage": stage.value}
                    )
                    migrated = True
            if item.id in loaded:
                raise DuplicateItemIdError(f"duplicate stored item ID: {item.id}")
            loaded[item.id] = item
        self._items = loaded
        if migrated:
            await self._storage.async_save(self._snapshot())

    def _snapshot(self) -> list[dict[str, Any]]:
        return [item.to_dict() for item in sorted(self._items.values(), key=lambda row: row.id)]

    async def _save(self) -> None:
        await self._storage.async_save(self._snapshot())
        self._notify()

    async def async_create_item(self, data: Mapping[str, Any]) -> ExpiryItem:
        item = ExpiryItem.create(data)
        async with self._lock:
            if item.id in self._items:
                raise DuplicateItemIdError(item.id)
            self._items[item.id] = item
            try:
                await self._save()
            except Exception:
                self._items.pop(item.id, None)
                raise
        await self._changed("create", item)
        return item

    async def async_update_item(self, item_id: str, changes: Mapping[str, Any]) -> ExpiryItem:
        async with self._lock:
            old = self.get_item(item_id)
            new = old.updated(changes)
            self._items[item_id] = new
            try:
                await self._save()
            except Exception:
                self._items[item_id] = old
                raise
        await self._changed("update", new)
        return new

    async def async_delete_item(self, item_id: str) -> ExpiryItem:
        async with self._lock:
            old = self.get_item(item_id)
            del self._items[item_id]
            try:
                await self._save()
            except Exception:
                self._items[item_id] = old
                raise
        await self._changed("delete", old)
        return old

    def get_item(self, item_id: str) -> ExpiryItem:
        if item_id not in self._items:
            raise ItemNotFoundError(item_id)
        return self._items[item_id]

    def list_items(self) -> list[ExpiryItem]:
        return sorted(self._items.values(), key=lambda row: (row.name.casefold(), row.id))

    def search(
        self,
        query: str,
        *,
        limit: int | None = 50,
        include_closed: bool = False,
    ) -> list[ExpiryItem]:
        terms = query.casefold().split()
        scored: list[tuple[int, str, ExpiryItem]] = []
        for item in self._items.values():
            if item.closed and not include_closed:
                continue
            fields = [item.name, item.category, *item.aliases]
            haystack = " ".join(fields).casefold()
            if not all(term in haystack for term in terms):
                continue
            score = (
                0
                if item.name.casefold() == query.casefold()
                else 1
                if item.name.casefold().startswith(query.casefold())
                else 2
            )
            scored.append((score, item.name.casefold(), item))
        ordered = sorted(scored, key=lambda row: (row[0], row[1], row[2].id))
        if limit is not None:
            ordered = ordered[:limit]
        return [row[2] for row in ordered]

    def query(
        self,
        today: date,
        *,
        start: date | None = None,
        end: date | None = None,
        actionable_only: bool = False,
        urgent_only: bool = False,
        expired_only: bool = False,
        important_only: bool = False,
        category: str | None = None,
        enabled_only: bool = True,
        include_closed: bool = False,
        limit: int = 500,
    ) -> list[tuple[ExpiryItem, ExpiryState]]:
        rows: list[tuple[ExpiryItem, ExpiryState]] = []
        for item in self._items.values():
            state = calculate_state(item, today)
            if (
                (not include_closed and item.closed)
                or (enabled_only and not item.enabled)
                or (category and item.category != category)
                or (important_only and not item.important)
            ):
                continue
            if (start and item.expiry_date < start) or (end and item.expiry_date > end):
                continue
            if (
                (actionable_only and not state.requires_attention)
                or (urgent_only and state.status != "urgent")
                or (expired_only and state.status != "expired")
            ):
                continue
            rows.append((item, state))
        return sorted(
            rows, key=lambda row: (row[0].expiry_date, row[0].name.casefold(), row[0].id)
        )[:limit]

    async def _replace_workflow(self, old: ExpiryItem, payload: dict[str, Any]) -> ExpiryItem:
        new = ExpiryItem.from_dict(payload)
        self._items[old.id] = new
        try:
            await self._save()
        except Exception:
            self._items[old.id] = old
            raise
        return new

    async def async_acknowledge(
        self,
        item_id: str,
        acknowledged: bool = True,
        stage: AttentionStage | str | None = None,
    ) -> ExpiryItem:
        async with self._lock:
            old = self.get_item(item_id)
            if old.closed:
                raise ValueError("closed items cannot be acknowledged")
            selected_stage = AttentionStage(stage) if stage is not None else None
            if acknowledged:
                current_stage = calculate_state(old, self._local_date(None)).attention_stage
                if selected_stage is None:
                    selected_stage = current_stage
                if selected_stage is None or selected_stage != current_stage:
                    raise ValueError("only the active attention stage can be acknowledged")
            acknowledged_stage: str | None = None
            if acknowledged:
                assert selected_stage is not None
                acknowledged_stage = selected_stage.value
            now = utc_now_iso()
            event = {
                "type": "acknowledged" if acknowledged else "acknowledgement_reset",
                "at": now,
                "stage": selected_stage.value if selected_stage else old.acknowledged_stage,
            }
            item = await self._replace_workflow(
                old,
                {
                    **old.to_dict(),
                    "acknowledged": acknowledged,
                    "acknowledged_stage": acknowledged_stage,
                    "acknowledged_at": now if acknowledged else None,
                    "history": [*old.history, event][-MAX_HISTORY:],
                    "updated_at": now,
                },
            )
        await self._changed("acknowledge", item)
        return item

    async def async_renew(self, item_id: str, new_expiry_date: date | None = None) -> ExpiryItem:
        async with self._lock:
            old = self.get_item(item_id)
            if old.closed:
                raise ValueError("closed items must be reopened before they can be renewed")
            if new_expiry_date is None:
                if old.recurrence_months is None:
                    raise ValueError(
                        "new_expiry_date is required when recurrence is not configured"
                    )
                new_expiry_date = add_months(old.expiry_date, old.recurrence_months)
                today = self._local_date(None)
                while new_expiry_date <= today:
                    new_expiry_date = add_months(new_expiry_date, old.recurrence_months)
            if new_expiry_date <= old.expiry_date:
                raise ValueError("new expiry date must be after the previous expiry date")
            now = utc_now_iso()
            history = [
                *old.history,
                {
                    "type": "renewed",
                    "at": now,
                    "previous_expiry_date": old.expiry_date.isoformat(),
                    "new_expiry_date": new_expiry_date.isoformat(),
                },
            ][-MAX_HISTORY:]
            payload = {
                **old.to_dict(),
                "expiry_date": new_expiry_date.isoformat(),
                "acknowledged": False,
                "acknowledged_stage": None,
                "acknowledged_at": None,
                "last_notifications": {},
                "history": history,
                "updated_at": now,
            }
            item = await self._replace_workflow(old, payload)
        await self._changed("renew", item)
        return item

    async def async_close(self, item_id: str, reason: str | None = None) -> ExpiryItem:
        async with self._lock:
            old = self.get_item(item_id)
            if old.closed:
                return old
            now = utc_now_iso()
            clean_reason = " ".join(reason.split()) if reason else None
            if clean_reason and len(clean_reason) > 4000:
                raise ValueError("close reason is too long")
            event = {"type": "closed", "at": now, "reason": clean_reason}
            item = await self._replace_workflow(
                old,
                {
                    **old.to_dict(),
                    "closed": True,
                    "closed_at": now,
                    "closed_reason": clean_reason,
                    "acknowledged": False,
                    "acknowledged_stage": None,
                    "acknowledged_at": None,
                    "last_notifications": {},
                    "history": [*old.history, event][-MAX_HISTORY:],
                    "updated_at": now,
                },
            )
        await self._changed("close", item)
        return item

    async def async_reopen(self, item_id: str) -> ExpiryItem:
        async with self._lock:
            old = self.get_item(item_id)
            if not old.closed:
                return old
            now = utc_now_iso()
            event = {"type": "reopened", "at": now}
            item = await self._replace_workflow(
                old,
                {
                    **old.to_dict(),
                    "closed": False,
                    "closed_at": None,
                    "closed_reason": None,
                    "last_notifications": {},
                    "history": [*old.history, event][-MAX_HISTORY:],
                    "updated_at": now,
                },
            )
        await self._changed("reopen", item)
        return item

    async def async_record_notification(self, item_id: str, event_key: str, timestamp: str) -> None:
        async with self._lock:
            old = self.get_item(item_id)
            await self._replace_workflow(
                old,
                {
                    **old.to_dict(),
                    "last_notifications": {**(old.last_notifications or {}), event_key: timestamp},
                    "updated_at": old.updated_at,
                },
            )

    def diagnostics_counts(self) -> dict[str, Any]:
        items = self.list_items()
        return {
            "item_count": len(items),
            "enabled_count": sum(i.enabled for i in items),
            "important_count": sum(i.important for i in items),
            "closed_count": sum(i.closed for i in items),
            "passive_count": sum(not i.requires_action for i in items),
            "exposed_entity_count": sum(i.expose_entity for i in items),
            "category_counts": dict(Counter(i.category for i in items)),
        }
