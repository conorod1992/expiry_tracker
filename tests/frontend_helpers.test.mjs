import assert from "node:assert/strict";
import test from "node:test";

import {
  STATUS_LABELS,
  addDays,
  addMonths,
  calculateActionDate,
  formatActionableDate,
  formatDate,
  groupItems,
  normalizeReminderThresholds,
  parseLocalDate,
  recurrenceLabel,
  relativeExpiry,
  reminderLabel,
  summarizeItems,
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

test("early years are preserved and immediate actionability hides the sentinel", () => {
  assert.equal(parseLocalDate("0001-01-01").getFullYear(), 1);
  assert.doesNotMatch(formatDate("0001-01-01", "en-IE"), /1901/);
  assert.equal(formatActionableDate("immediate", "0001-01-01", "en-IE"), "Any time");
  assert.equal(formatActionableDate("date", "2027-03-14", "en-IE"), "14 March 2027");
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

test("arbitrary reminder thresholds are preserved, deduplicated, and validated", () => {
  assert.deepEqual(normalizeReminderThresholds([45, "100", 10, 45, 0]), [100, 45, 10, 0]);
  assert.throws(() => normalizeReminderThresholds([Number.NaN]), /whole numbers/);
  assert.throws(() => normalizeReminderThresholds([-1]), /whole numbers/);
  assert.throws(() => normalizeReminderThresholds([2.5]), /whole numbers/);
});

test("task groups separate acknowledged items that are still outstanding", () => {
  const attention = { id: "a", enabled: true, acknowledged: false, requires_attention: true, status: "actionable", important: false, days_until_expiry: 20 };
  const urgentAttention = { id: "h", enabled: true, acknowledged: false, requires_attention: false, status: "urgent", important: false, days_until_expiry: 3 };
  const expiredAttention = { id: "i", enabled: true, acknowledged: false, requires_attention: false, status: "expired", important: false, days_until_expiry: -3 };
  const acknowledgedActionable = { id: "b", enabled: true, acknowledged: true, requires_attention: false, status: "actionable", important: false, days_until_expiry: 20 };
  const acknowledgedUrgent = { id: "c", enabled: true, acknowledged: true, requires_attention: false, status: "urgent", important: false, days_until_expiry: 3 };
  const acknowledgedExpired = { id: "d", enabled: true, acknowledged: true, requires_attention: false, status: "expired", important: false, days_until_expiry: -3 };
  const warning = { id: "e", enabled: true, acknowledged: false, requires_attention: false, status: "warning", important: false, days_until_expiry: 100 };
  const later = { id: "f", enabled: true, acknowledged: false, requires_attention: false, status: "valid", important: false, days_until_expiry: 400 };
  const disabled = { id: "g", enabled: false, acknowledged: true, requires_attention: false, status: "expired", important: true, days_until_expiry: -3 };
  const grouped = groupItems([later, warning, acknowledgedExpired, attention, urgentAttention, expiredAttention, disabled, acknowledgedUrgent, acknowledgedActionable]);
  assert.deepEqual(grouped.attention.map((item) => item.id), ["a", "h", "i"]);
  assert.deepEqual(grouped.acknowledged.map((item) => item.id), ["d", "c", "b"]);
  assert.deepEqual(grouped.comingUp.map((item) => item.id), ["e"]);
  assert.deepEqual(grouped.later.map((item) => item.id), ["f", "g"]);
});

test("global summary does not inherit a filtered card subset", () => {
  const insurance = { id: "a", enabled: true, requires_attention: true, status: "urgent", days_until_expiry: 5, expiry_date: "2026-08-25" };
  const pet = { id: "b", enabled: true, requires_attention: false, status: "valid", days_until_expiry: 100, expiry_date: "2026-11-28" };
  const filteredCards = [pet];
  assert.equal(summarizeItems([insurance, pet]).attention, 1);
  assert.equal(summarizeItems([insurance, pet]).urgent, 1);
  assert.equal(summarizeItems([insurance, pet]).next.id, "a");
  assert.equal(summarizeItems(filteredCards).attention, 0);
});
