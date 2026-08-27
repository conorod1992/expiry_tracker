import assert from "node:assert/strict";
import test from "node:test";

import {
  actionInfo,
  matchingAlias,
} from "../custom_components/expiry_tracker/frontend/expiry-tracker-workflow-helpers.mjs";

test("actionInfo keeps renew backwards compatible", () => {
  assert.deepEqual(actionInfo({}), {
    value: "renew",
    label: "Renew",
    completed: "renewed",
    button: "Mark as renewed",
  });
});

test("actionInfo supports configured and custom completion wording", () => {
  assert.equal(actionInfo({ action_type: "review" }).button, "Mark as reviewed");
  assert.equal(
    actionInfo({ action_type: "custom", custom_action_label: "serviced" }).button,
    "Mark as serviced",
  );
});

test("matchingAlias returns the visible matching alias", () => {
  const item = { aliases: ["Driving licence", "ADI permit"] };
  assert.equal(matchingAlias(item, "permit"), "ADI permit");
  assert.equal(matchingAlias(item, "passport"), null);
  assert.equal(matchingAlias(item, ""), null);
});
