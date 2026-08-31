import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const dashboardSource = await readFile(
  new URL("../custom_components/expiry_tracker/frontend/expiry-tracker-dashboard.js", import.meta.url),
  "utf8",
);
const enhancedSource = await readFile(
  new URL("../custom_components/expiry_tracker/frontend/expiry-tracker-panel-enhanced.js", import.meta.url),
  "utf8",
);
const constSource = await readFile(
  new URL("../custom_components/expiry_tracker/const.py", import.meta.url),
  "utf8",
);
const setupSource = await readFile(
  new URL("../custom_components/expiry_tracker/__init__.py", import.meta.url),
  "utf8",
);

test("frontend cache busting versions the static root used by every relative import", () => {
  assert.match(constSource, /PANEL_STATIC_URL: Final = f"\/expiry_tracker_static\/\{VERSION\}"/);
  assert.match(setupSource, /StaticPathConfig\(PANEL_STATIC_URL, str\(path\), True\)/);
  assert.match(setupSource, /module_url=f"\{PANEL_STATIC_URL\}\/expiry-tracker-dashboard\.js"/);
  assert.doesNotMatch(setupSource, /expiry-tracker-dashboard\.js\?v=/);
});

test("native repeat UI exposes one control while synchronizing the legacy field", () => {
  assert.match(enhancedSource, /<strong>Repeat until dismissed<\/strong>/);
  assert.match(
    enhancedSource,
    /name="repeat_until_acknowledged" hidden aria-hidden="true" tabindex="-1"/,
  );
  assert.match(enhancedSource, /legacyRepeat\.checked = repeat\.checked/);
  assert.doesNotMatch(enhancedSource, /Repeat reminders until dismissed/);
});

test("delivery switching tolerates reload interruptions and waits by condition", () => {
  assert.match(enhancedSource, /const deadline = Date\.now\(\) \+ 30000/);
  assert.match(enhancedSource, /while \(Date\.now\(\) < deadline\)/);
  assert.match(enhancedSource, /lastError = error/);
  assert.match(enhancedSource, /Math\.min\(Math\.round\(delay \* 1\.5\), 1500\)/);
  assert.doesNotMatch(enhancedSource, /attempt < 20/);
});

test("bulk actions continue after failures and keep failed items selected", () => {
  assert.match(dashboardSource, /const succeeded = \[\]/);
  assert.match(dashboardSource, /const failed = \[\]/);
  assert.match(dashboardSource, /failed\.push\(\{ item, error \}\)/);
  assert.match(dashboardSource, /state\.selected = new Set\(failed\.map/);
  assert.match(dashboardSource, /failed items remain selected/);
  assert.match(dashboardSource, /<strong>Archived items<\/strong>/);
  assert.match(dashboardSource, />Archive<\/button>/);
  assert.doesNotMatch(dashboardSource, /Closed \/ archive/);
});
