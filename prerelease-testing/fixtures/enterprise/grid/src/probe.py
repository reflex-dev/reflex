"""Render-time probe for window.__reflex (verifier fixture, shared by corev and entv).

ReflexProbe is a tiny React function component defined via inline custom code. On every
render it records (into window.__trace) whether window.__reflex is defined AT RENDER
TIME, a per-label render counter and a performance.now() timestamp, and renders
`<label>|HAS_REFLEX|<json value>` or `<label>|NO_REFLEX|<json value>`. The DOM text does
not contain the counter so that prerendered HTML and the first client render match.
"""

from typing import Any

import reflex as rx

PROBE_JS = r"""
function ReflexProbe({label, value}) {
  const isClient = typeof window !== "undefined";
  const has = isClient && typeof window.__reflex !== "undefined";
  if (isClient) {
    window.__probeCounts = window.__probeCounts || {};
    const n = (window.__probeCounts[label] = (window.__probeCounts[label] || 0) + 1);
    (window.__trace = window.__trace || []).push({
      ev: "probe_render", label, n, has, t: performance.now(),
      value: JSON.stringify(value === undefined ? null : value),
    });
  }
  const tag = has ? "HAS_REFLEX" : "NO_REFLEX";
  return createElement(
    "span",
    {id: "probe-" + label, "data-has": tag, style: {display: "block", fontFamily: "monospace"}},
    label + "|" + tag + "|" + JSON.stringify(value === undefined ? null : value),
  );
}
"""


class ReflexProbe(rx.Component):
    """A component that reports whether window.__reflex exists when it renders."""

    tag = "ReflexProbe"

    label: rx.Var[str]
    value: rx.Var[Any]

    def _get_custom_code(self) -> str | None:
        return PROBE_JS

    def add_imports(self):
        return {"react": [rx.ImportVar(tag="createElement")]}


reflex_probe = ReflexProbe.create
