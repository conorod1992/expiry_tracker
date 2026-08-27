export const ACTION_TYPES = [
  ["renew", "Renew", "renewed"],
  ["replace", "Replace", "replaced"],
  ["review", "Review", "reviewed"],
  ["retest", "Re-test", "re-tested"],
  ["reregister", "Re-register", "re-registered"],
  ["cancel", "Cancel / end", "cancelled"],
  ["check", "Check", "checked"],
  ["custom", "Custom", "completed"],
];

const ACTION_MAP = Object.fromEntries(
  ACTION_TYPES.map(([value, label, completed]) => [value, { value, label, completed }]),
);

export function actionInfo(item = {}) {
  const type = ACTION_MAP[item.action_type] ? item.action_type : "renew";
  const definition = ACTION_MAP[type];
  if (type !== "custom") {
    return {
      ...definition,
      button: `Mark as ${definition.completed}`,
    };
  }
  const custom = String(item.custom_action_label || "completed").trim() || "completed";
  return {
    ...definition,
    completed: custom,
    button: `Mark as ${custom}`,
  };
}

export function matchingAlias(item = {}, query = "") {
  const normalized = String(query).trim().toLocaleLowerCase();
  if (!normalized) return null;
  return (item.aliases || []).find((alias) =>
    String(alias).toLocaleLowerCase().includes(normalized),
  ) || null;
}
