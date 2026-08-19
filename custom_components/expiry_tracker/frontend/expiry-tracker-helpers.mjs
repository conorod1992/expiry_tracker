const DAY_MS = 86_400_000;

export const STATUS_LABELS = Object.freeze({
  valid: "All good",
  warning: "Coming up",
  actionable: "Ready to deal with",
  urgent: "Urgent",
  expired: "Expired",
});

export function parseLocalDate(value) {
  if (!value) return null;
  const [year, month, day] = String(value).slice(0, 10).split("-").map(Number);
  if (!year || !month || !day) return null;
  const parsed = new Date(2000, 0, 1, 12);
  parsed.setFullYear(year, month - 1, day);
  if (
    parsed.getFullYear() !== year ||
    parsed.getMonth() !== month - 1 ||
    parsed.getDate() !== day
  ) {
    return null;
  }
  return parsed;
}

export function toIsoDate(value) {
  if (!(value instanceof Date) || Number.isNaN(value.valueOf())) return "";
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function formatDate(value, locale, compact = false) {
  const parsed = parseLocalDate(value);
  if (!parsed) return "Not set";
  return new Intl.DateTimeFormat(locale, {
    day: "numeric",
    month: compact ? "short" : "long",
    year: "numeric",
  }).format(parsed);
}

export function formatDateTime(value, locale) {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) return "";
  return new Intl.DateTimeFormat(locale, {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parsed);
}

export function formatActionableDate(mode, value, locale) {
  return mode === "immediate" ? "Any time" : formatDate(value, locale);
}

export function relativeExpiry(days) {
  if (days === 0) return "Expires today";
  if (days === 1) return "1 day left";
  if (days > 1) return `${days} days left`;
  if (days === -1) return "Expired yesterday";
  return `Expired ${Math.abs(days)} days ago`;
}

export function relativeFutureDate(value, now = new Date()) {
  const parsed = parseLocalDate(value);
  if (!parsed) return "";
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 12);
  const days = Math.round((parsed - today) / DAY_MS);
  if (days <= 0) return "You can deal with this now";
  if (days === 1) return "You can deal with this tomorrow";
  if (days < 60) return `You can deal with this in ${days} days`;
  const months = Math.max(2, Math.round(days / 30.4375));
  return `You can deal with this in about ${months} months`;
}

export function reminderLabel(days) {
  const known = new Map([
    [365, "1 year before"],
    [180, "6 months before"],
    [90, "3 months before"],
    [60, "2 months before"],
    [30, "1 month before"],
    [14, "2 weeks before"],
    [7, "1 week before"],
    [3, "3 days before"],
    [1, "1 day before"],
    [0, "On the expiry date"],
  ]);
  return known.get(Number(days)) || `${days} days before`;
}

export function recurrenceLabel(months) {
  if (!months) return "I'll enter the new date myself";
  if (months % 12 === 0) {
    const years = months / 12;
    return `${years} year${years === 1 ? "" : "s"}`;
  }
  return `${months} months`;
}

export function normalizeReminderThresholds(values) {
  const thresholds = values.map(Number);
  if (thresholds.some((value) => !Number.isInteger(value) || value < 0)) {
    throw new TypeError("Reminder thresholds must be whole numbers of zero or more days");
  }
  return [...new Set(thresholds)].sort((left, right) => right - left);
}

export function addMonths(value, months) {
  const parsed = parseLocalDate(value);
  if (!parsed || !months) return "";
  const originalDay = parsed.getDate();
  parsed.setDate(1);
  parsed.setMonth(parsed.getMonth() + Number(months));
  const finalDay = new Date(parsed.getFullYear(), parsed.getMonth() + 1, 0).getDate();
  parsed.setDate(Math.min(originalDay, finalDay));
  return toIsoDate(parsed);
}

export function addDays(value, days) {
  const parsed = parseLocalDate(value);
  if (!parsed) return "";
  parsed.setDate(parsed.getDate() + Number(days));
  return toIsoDate(parsed);
}

export function subtractMonths(value, months) {
  return addMonths(value, -Number(months));
}

export function calculateActionDate(expiry, mode, amount, unit, specificDate) {
  if (!expiry) return "";
  if (mode === "immediate") return "anytime";
  if (mode === "date") return specificDate || "";
  if (unit === "months") return subtractMonths(expiry, Number(amount || 0));
  const parsed = parseLocalDate(expiry);
  if (!parsed) return "";
  parsed.setDate(parsed.getDate() - Number(amount || 0));
  return toIsoDate(parsed);
}

export function groupItems(items) {
  const groups = { attention: [], acknowledged: [], comingUp: [], later: [] };
  for (const item of items) {
    const outstanding = ["actionable", "urgent", "expired"].includes(item.status);
    if (item.enabled && !item.acknowledged && (item.requires_attention || outstanding)) {
      groups.attention.push(item);
    } else if (item.enabled && item.acknowledged && outstanding) {
      groups.acknowledged.push(item);
    } else if (
      item.enabled &&
      (item.status !== "valid" || item.important || item.days_until_expiry <= 180)
    ) {
      groups.comingUp.push(item);
    } else {
      groups.later.push(item);
    }
  }
  return groups;
}

export function summarizeItems(items) {
  const enabled = items.filter((item) => item.enabled);
  return {
    attention: enabled.filter((item) => item.requires_attention).length,
    urgent: enabled.filter((item) => item.status === "urgent").length,
    next: enabled
      .filter((item) => item.days_until_expiry >= 0)
      .sort((left, right) => left.expiry_date.localeCompare(right.expiry_date))[0],
  };
}
