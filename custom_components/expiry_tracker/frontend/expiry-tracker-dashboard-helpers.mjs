export function nextDealableItem(items = []) {
  const active = items.filter((item) => item.enabled && !item.closed && item.requires_action !== false);
  const ready = active.filter((item) => item.actionable || item.requires_attention);
  if (ready.length) {
    return ready.sort((a, b) =>
      String(a.expiry_date).localeCompare(String(b.expiry_date)) ||
      String(a.name).localeCompare(String(b.name)),
    )[0];
  }
  return active
    .filter((item) => item.actionable_date)
    .sort((a, b) =>
      String(a.actionable_date).localeCompare(String(b.actionable_date)) ||
      String(a.expiry_date).localeCompare(String(b.expiry_date)),
    )[0] || null;
}

export function timelineRows(items = []) {
  return items
    .filter((item) => item.enabled && !item.closed)
    .slice()
    .sort((a, b) =>
      String(a.expiry_date).localeCompare(String(b.expiry_date)) ||
      String(a.name).localeCompare(String(b.name)),
    );
}

export function configurationWarnings({ expiryDate, actionableDate, urgentDate, warningDates = [] } = {}) {
  const warnings = [];
  if (actionableDate && urgentDate && urgentDate < actionableDate) {
    warnings.push("The urgent stage begins before this item can be dealt with.");
  }
  if (expiryDate && actionableDate && actionableDate > expiryDate) {
    warnings.push("The action date is after the expiry date.");
  }
  if (warningDates.some((value) => expiryDate && value > expiryDate)) {
    warnings.push("A reminder is scheduled after the expiry date.");
  }
  return warnings;
}

export function selectedItems(items = [], selectedIds = new Set()) {
  return items.filter((item) => selectedIds.has(item.id));
}
