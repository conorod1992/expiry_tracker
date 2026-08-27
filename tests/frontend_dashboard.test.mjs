import assert from "node:assert/strict";
import test from "node:test";

import {
  configurationWarnings,
  nextDealableItem,
  selectedItems,
  timelineRows,
} from "../custom_components/expiry_tracker/frontend/expiry-tracker-dashboard-helpers.mjs";

test("next dealable item prefers work that is ready now", () => {
  const future = {
    id: "future",
    name: "Future",
    enabled: true,
    closed: false,
    requires_action: true,
    actionable: false,
    actionable_date: "2026-09-01",
    expiry_date: "2026-10-01",
  };
  const ready = {
    id: "ready",
    name: "Ready",
    enabled: true,
    closed: false,
    requires_action: true,
    actionable: true,
    actionable_date: "2026-08-01",
    expiry_date: "2026-09-15",
  };
  assert.equal(nextDealableItem([future, ready]).id, "ready");
});

test("next dealable item ignores passive, closed, and disabled items", () => {
  const rows = [
    { id: "passive", enabled: true, closed: false, requires_action: false, actionable_date: "2026-08-01", expiry_date: "2026-09-01", name: "Passive" },
    { id: "closed", enabled: true, closed: true, requires_action: true, actionable_date: "2026-08-01", expiry_date: "2026-09-01", name: "Closed" },
    { id: "disabled", enabled: false, closed: false, requires_action: true, actionable_date: "2026-08-01", expiry_date: "2026-09-01", name: "Disabled" },
    { id: "active", enabled: true, closed: false, requires_action: true, actionable_date: "2026-09-10", expiry_date: "2026-10-01", name: "Active" },
  ];
  assert.equal(nextDealableItem(rows).id, "active");
});

test("timeline sorts active items by expiry and omits archived items", () => {
  const rows = timelineRows([
    { id: "b", enabled: true, closed: false, expiry_date: "2026-10-01", name: "B" },
    { id: "closed", enabled: true, closed: true, expiry_date: "2026-08-01", name: "Closed" },
    { id: "a", enabled: true, closed: false, expiry_date: "2026-09-01", name: "A" },
  ]);
  assert.deepEqual(rows.map((row) => row.id), ["a", "b"]);
});

test("configuration warning catches urgent-before-actionable without blocking valid config", () => {
  assert.deepEqual(
    configurationWarnings({
      expiryDate: "2026-12-31",
      actionableDate: "2026-12-01",
      urgentDate: "2026-11-15",
    }),
    ["The urgent stage begins before this item can be dealt with."],
  );
  assert.deepEqual(
    configurationWarnings({
      expiryDate: "2026-12-31",
      actionableDate: "2026-11-01",
      urgentDate: "2026-12-15",
    }),
    [],
  );
});

test("bulk selection resolves only currently supplied items", () => {
  const rows = [{ id: "a" }, { id: "b" }, { id: "c" }];
  assert.deepEqual(selectedItems(rows, new Set(["b", "missing"])), [{ id: "b" }]);
});
