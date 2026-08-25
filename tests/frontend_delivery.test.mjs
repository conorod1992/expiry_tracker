import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import test from "node:test";

const source = await readFile(
  new URL("../custom_components/expiry_tracker/frontend/expiry-tracker-panel.js", import.meta.url),
  "utf8",
);

test("delivery UI describes both backends and exposes the existing option only when available", () => {
  assert.match(source, /Delivered by Reminders/);
  assert.match(source, /Using built-in notifications/);
  assert.match(source, /settings\.capabilities\?\.reminders_available/);
  assert.match(source, /data-use-reminders/);
  assert.match(source, /update_delivery",\{use_reminders:element\.checked\}/);
  assert.doesNotMatch(source, /localStorage|sessionStorage/);
});

test("Reminders mode retains milestone controls while hiding native delivery controls", () => {
  assert.match(source, /native-reminder-controls" \$\{active\?"hidden":""\}/);
  assert.match(source, /require_acknowledgement/);
  assert.match(source, /repeat_until_acknowledged/);
  assert.match(source, /repeat_interval_hours/);
  assert.match(source, /warning_thresholds/);
  assert.match(source, /notify_actionable/);
  assert.match(source, /notify_urgent/);
  assert.match(source, /notify_expiry/);
  assert.match(source, /urgent_days_before/);
});
