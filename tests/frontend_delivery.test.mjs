import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import test from "node:test";

const source = await readFile(
  new URL("../custom_components/expiry_tracker/frontend/expiry-tracker-panel.js", import.meta.url),
  "utf8",
);

test("panel-level delivery UI is admin-only, capability-gated, and uses no new storage", () => {
  assert.match(source, /Delivered by Reminders/);
  assert.match(source, /Using built-in notifications/);
  assert.match(source, /settings\.capabilities\?\.reminders_available/);
  assert.match(source, /this\.view!=="form"&&this\.settings\.is_admin/);
  assert.match(source, /data-use-reminders/);
  assert.match(source, /update_delivery",\{use_reminders:useReminders\}/);
  assert.doesNotMatch(source, /localStorage|sessionStorage/);
});

test("item forms retain delivery information but never include the global toggle", () => {
  const formReminders = source.match(/formReminders\(item,reminders\)\{([\s\S]*?)\n  formRenewal/)[1];
  assert.match(formReminders, /Delivered by Reminders/);
  assert.match(formReminders, /Using built-in notifications/);
  assert.doesNotMatch(formReminders, /data-use-reminders|Use Reminders for delivery/);
});

test("delivery switch remains pending until refreshed backend capabilities confirm it", () => {
  assert.match(source, /Switching to Reminders…/);
  assert.match(source, /Switching to built-in notifications…/);
  assert.match(source, /await this\.refreshDeliverySettings\(useReminders\)/);
  assert.match(source, /settings\.capabilities\?\.delivery_backend===backend/);
  assert.doesNotMatch(source, /this\.settings=await this\.call\("update_delivery"/);
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
