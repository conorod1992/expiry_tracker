import assert from "node:assert/strict";
import test from "node:test";

import {
  STATUS_LABELS,
  addDays,
  addMonths,
  calculateActionDate,
  formatDate,
  groupItems,
  recurrenceLabel,
  relativeExpiry,
  reminderLabel,
} from "../custom_components/expiry_tracker/frontend/expiry-tracker-helpers.mjs";

test("status labels hide internal terminology", () => {
  assert.equal(STATUS_LABELS.valid, "All good");
  assert.equal(STATUS_LABELS.actionable, "Ready to deal with");
});

test("dates and relative expiry text are human readable", () => {
  assert.equal(formatDate("2027-03-14", "en-IE"), "14 March 2027");
  assert.equal(relativeExpiry(0), "Expires today");
  assert.equal(relativeExpiry(12), "12 days left");
  assert.equal(relativeExpiry(-3), "Expired 3 days ago");
});

test("renewal suggestions clamp calendar month boundaries", () => {
  assert.equal(addMonths("2024-02-29", 12), "2025-02-28");
  assert.equal(addMonths("2025-01-31", 1), "2025-02-28");
  assert.equal(addDays("2024-02-28", 1), "2024-02-29");
  assert.equal(calculateActionDate("2025-03-31", "offset", 1, "months", ""), "2025-02-28");
});

test("friendly reminder and renewal labels retain backend values", () => {
  assert.equal(reminderLabel(180), "6 months before");
  assert.equal(reminderLabel(23), "23 days before");
  assert.equal(recurrenceLabel(null), "I'll enter the new date myself");
  assert.equal(recurrenceLabel(36), "3 years");
});

test("task groups prioritize unacknowledged items requiring attention", () => {
  const attention = { id: "a", enabled: true, requires_attention: true, status: "urgent", important: false, days_until_expiry: 5 };
  const acknowledged = { id: "b", enabled: true, requires_attention: false, status: "actionable", important: false, days_until_expiry: 20 };
  const later = { id: "c", enabled: true, requires_attention: false, status: "valid", important: false, days_until_expiry: 400 };
  const disabled = { id: "d", enabled: false, requires_attention: false, status: "valid", important: true, days_until_expiry: 3 };
  const grouped = groupItems([later, acknowledged, attention, disabled]);
  assert.deepEqual(grouped.attention.map((item) => item.id), ["a"]);
  assert.deepEqual(grouped.comingUp.map((item) => item.id), ["b"]);
  assert.deepEqual(grouped.later.map((item) => item.id), ["c", "d"]);
});
