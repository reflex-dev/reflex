import { createElement } from "react";

// Explicit locale/timezone keep publication dates identical during prerendering
// and in the browser, including visitors west of UTC on date-only API values.
export function formatPublicationDate(value, compact = false) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const parts = new Intl.DateTimeFormat("en-US", {
    month: "short", day: compact ? "2-digit" : "numeric", year: "numeric", timeZone: "UTC",
  }).formatToParts(date);
  const part = (type) => parts.find((p) => p.type === type).value;
  return `${part("month")} ${part("day")}${compact ? "" : ","} ${part("year")}`;
}

export function MarketingDate({ value, compact = false, className }) {
  return createElement("time", { dateTime: value, className }, formatPublicationDate(value, compact));
}
