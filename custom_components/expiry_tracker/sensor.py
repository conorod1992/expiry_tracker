"""Aggregate and stable optional per-item sensors."""

from __future__ import annotations

from datetime import date
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .calculations import ExpiryState, calculate_state
from .const import DOMAIN, SIGNAL_UPDATED
from .helpers import local_today
from .manager import ExpiryTrackerManager
from .models import ExpiryItem


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[ExpiryTrackerManager],
    async_add_entities: AddEntitiesCallback,
) -> None:
    manager = entry.runtime_data
    aggregates: list[SensorEntity] = [
        NextExpirySensor(manager, actionable=False),
        NextExpirySensor(manager, actionable=True),
        StatusCountSensor(manager, "actionable"),
        StatusCountSensor(manager, "urgent"),
        StatusCountSensor(manager, "expired"),
    ]
    async_add_entities(aggregates)
    active: dict[str, ExpiryItemSensor] = {}

    @callback
    def reconcile() -> None:
        hass.async_create_task(_reconcile(), "expiry_tracker_reconcile_sensors")

    async def _reconcile() -> None:
        desired = {
            item.id
            for item in manager.list_items()
            if item.enabled and not item.closed and item.expose_entity
        }
        for item_id, entity in list(active.items()):
            if item_id not in desired:
                active.pop(item_id)
                await entity.async_remove()
                try:
                    manager.get_item(item_id)
                except KeyError:
                    registry = er.async_get(hass)
                    entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"item_{item_id}")
                    if entity_id:
                        registry.async_remove(entity_id)
        new = []
        for item_id in desired - active.keys():
            active[item_id] = ExpiryItemSensor(manager, item_id)
            new.append(active[item_id])
        if new:
            async_add_entities(new)
        for state_entity in [*aggregates, *active.values()]:
            if state_entity.hass is not None:
                state_entity.async_write_ha_state()

    entry.async_on_unload(async_dispatcher_connect(hass, SIGNAL_UPDATED, reconcile))
    await _reconcile()


class NextExpirySensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.DATE
    _attr_icon = "mdi:calendar-arrow-right"

    def __init__(self, manager: ExpiryTrackerManager, *, actionable: bool) -> None:
        self._manager = manager
        self._actionable = actionable
        self._attr_unique_id = "next_actionable_expiry" if actionable else "next_expiry"
        self._attr_name = "Next actionable expiry" if actionable else "Next expiry"

    def _value(self) -> tuple[ExpiryItem, ExpiryState] | None:
        today = local_today()
        rows = [
            (item, calculate_state(item, today))
            for item in self._manager.list_items()
            if item.enabled
            and not item.closed
            and (self._actionable or item.expiry_date >= today)
        ]
        if self._actionable:
            rows = [row for row in rows if row[1].requires_attention]
        return min(rows, key=lambda row: (row[0].expiry_date, row[0].id)) if rows else None

    @property
    def native_value(self) -> date | None:
        row = self._value()
        return row[0].expiry_date if row else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        row = self._value()
        if not row:
            return {}
        item, state = row
        return {
            "item_id": item.id,
            "name": item.name,
            "category": item.category,
            "days_until_expiry": state.days_until_expiry,
            "status": state.status.value,
            "requires_attention": state.requires_attention,
            "renewal_outstanding": state.renewal_outstanding,
        }


class StatusCountSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "items"

    def __init__(self, manager: ExpiryTrackerManager, kind: str) -> None:
        self._manager = manager
        self._kind = kind
        self._attr_unique_id = f"expiry_tracker_{kind}"
        self._attr_name = kind.title()
        self._attr_icon = {
            "actionable": "mdi:clipboard-alert",
            "urgent": "mdi:alert",
            "expired": "mdi:calendar-remove",
        }[kind]

    @property
    def native_value(self) -> int:
        today = local_today()
        states = [
            calculate_state(item, today)
            for item in self._manager.list_items()
            if item.enabled and not item.closed
        ]
        if self._kind == "actionable":
            return sum(state.requires_attention for state in states)
        if self._kind == "urgent":
            return sum(state.status.value == "urgent" for state in states)
        return sum(state.status.value == "expired" for state in states)


class ExpiryItemSensor(SensorEntity):
    _attr_has_entity_name = False
    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, manager: ExpiryTrackerManager, item_id: str) -> None:
        self._manager = manager
        self._item_id = item_id
        self._attr_unique_id = f"item_{item_id}"

    @property
    def _item(self) -> ExpiryItem:
        return self._manager.get_item(self._item_id)

    @property
    def name(self) -> str:
        return self._item.name

    @property
    def icon(self) -> str:
        return "mdi:calendar-clock"

    @property
    def native_value(self) -> date:
        return self._item.expiry_date

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        item = self._item
        state = calculate_state(item, local_today())
        return {
            "item_id": item.id,
            "expiry_date": item.expiry_date.isoformat(),
            "days_until_expiry": state.days_until_expiry,
            "status": state.status.value,
            "actionable": state.actionable,
            "actionable_date": state.actionable_date.isoformat(),
            "urgent_date": state.urgent_date.isoformat(),
            "attention_stage": state.attention_stage.value if state.attention_stage else None,
            "acknowledged": state.acknowledged,
            "acknowledged_stage": item.acknowledged_stage,
            "acknowledged_at": item.acknowledged_at,
            "requires_action": item.requires_action,
            "renewal_outstanding": state.renewal_outstanding,
            "category": item.category,
            "important": item.important,
        }
