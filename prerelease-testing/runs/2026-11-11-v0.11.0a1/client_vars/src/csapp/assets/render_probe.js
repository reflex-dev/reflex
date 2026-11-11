import { createElement, useEffect } from "react";

// Renders <span id=...>{value}</span> and counts its own commits in window.__rc[name].
export function RenderProbe({ name, value, id, className }) {
  useEffect(() => {
    window.__rc = window.__rc || {};
    window.__rc[name] = (window.__rc[name] || 0) + 1;
  });
  return createElement("span", { id, className, "data-probe": name }, value === undefined || value === null ? "" : String(value));
}
