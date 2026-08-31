import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(
  new URL(
    "../custom_components/expiry_tracker/frontend/expiry-tracker-panel-enhanced.js",
    import.meta.url,
  ),
  "utf8",
);

test("passive items use informational grouping and wording", () => {
  assert.match(source, /groups\.informational/);
  assert.match(source, /Expired — no action needed/);
  assert.match(source, /Tracked for reference — no action required/);
  assert.match(source, /Informational tracking only/);
});

test("passive items suppress attention actions and actionable dates", () => {
  assert.match(source, /quickActions && !passive/);
  assert.match(source, /actionable_date: null/);
  assert.match(source, /attention_stage: null/);
  assert.match(source, /no dismissal needed/);
  assert.match(source, /No repeated attention reminders/);
});

test("passive detail view removes completion workflow language", () => {
  assert.match(source, /Tracking settings/);
  assert.match(source, /Mode<\/dt><dd>Informational only/);
  assert.match(source, /Edit the item when the tracked expiry changes/);
  assert.match(source, /will not treat it as work you need to complete or a reminder you need to dismiss/);
});
