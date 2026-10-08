"""Shared Playwright helpers for the hydration cluster drivers (run with $SB/envs/driver python)."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

CHROMIUM = "/opt/pw-browsers/chromium"

BENIGN_CONSOLE = [
    re.compile(r"Hey developer.*HydrateFallback|reactrouter\.com/start/framework/route-module"),
    re.compile(r"\[vite\] (connecting|connected)"),
    re.compile(r"Download the React DevTools"),
]

TRACKED_IDS = [
    "hyd-flag", "ls-plain", "ls-sync", "ss-val", "ck-val", "ck-int", "ck-int-plus", "ls-same",
    "big-len", "sub-ls", "sub-ck", "sub-ss", "sub-uuid", "clean-ls", "clean-ck", "load-count",
    "counter", "gate-content", "gate-spinner", "gate-loads", "d-session-id", "d-created", "d-env",
    "d-items", "d-pid", "d-summary", "d-mapping", "d-point", "d-flt", "d-fixed-dt",
    "slow-progress", "slow-progress-other", "slow-progress-upload", "bg-status", "cf-log",
    "cf-gated", "cf-wait", "lsl-val", "lsl-saw", "box-a-ls", "box-b-ls", "other-count",
    "item-trace", "item-params", "docs-trace", "multi-order", "script-result", "up-status",
    "nested-log", "sub-saw",
]

TIMELINE_JS = """
(() => {
  if (window.__hyd) return;
  window.__hyd = { log: [], last: {} };
  const ids = %s;
  const snap = () => {
    for (const id of ids) {
      const el = document.getElementById(id);
      const v = el ? el.textContent : null;
      if (window.__hyd.last[id] !== v) {
        window.__hyd.last[id] = v;
        window.__hyd.log.push([Math.round(performance.now()), id, v === null ? null : v.slice(0, 300)]);
      }
    }
  };
  const start = () => {
    snap();
    new MutationObserver(snap).observe(document.documentElement,
      {subtree: true, childList: true, characterData: true});
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
""" % json.dumps(TRACKED_IDS)


def is_benign(text: str) -> bool:
    """Return True for known-benign console chatter."""
    return any(p.search(text) for p in BENIGN_CONSOLE)


class Recorder:
    """Collects console, page errors, failed requests, HTTP errors and websocket frames."""

    def __init__(self) -> None:
        self.t0 = time.time()
        self.console: list[dict] = []
        self.pageerrors: list[dict] = []
        self.failed: list[dict] = []
        self.http_errors: list[dict] = []
        self.ws_frames: list[dict] = []
        self.ws_events: list[dict] = []

    def now(self) -> float:
        return round(time.time() - self.t0, 3)

    def attach(self, page, tag: str) -> None:
        page.on("console", lambda m: self.console.append(
            {"tag": tag, "t": self.now(), "type": m.type, "text": m.text[:1500]}))
        page.on("pageerror", lambda e: self.pageerrors.append(
            {"tag": tag, "t": self.now(), "error": str(e)[:1500]}))
        page.on("requestfailed", lambda r: self.failed.append(
            {"tag": tag, "t": self.now(), "url": r.url, "failure": r.failure}))
        page.on("response", lambda r: r.status >= 400 and self.http_errors.append(
            {"tag": tag, "t": self.now(), "url": r.url, "status": r.status}))
        page.on("websocket", lambda ws: self._ws(ws, tag))

    def _ws(self, ws, tag: str) -> None:
        if "_event" not in ws.url:
            return
        wall = lambda: time.time() * 1000.0  # noqa: E731
        self.ws_events.append({"tag": tag, "t": self.now(), "ev": "open", "url": ws.url})
        ws.on("framesent", lambda p: self.ws_frames.append(
            {"tag": tag, "t": self.now(), "wall": wall(), "dir": "out", "len": len(p), "p": p if len(p) < 4000 else p[:4000] + "...<trunc>"}))
        ws.on("framereceived", lambda p: self.ws_frames.append(
            {"tag": tag, "t": self.now(), "wall": wall(), "dir": "in", "len": len(p), "p": p if len(p) < 4000 else p[:4000] + "...<trunc>"}))
        ws.on("close", lambda w: self.ws_events.append({"tag": tag, "t": self.now(), "ev": "close"}))
        ws.on("socketerror", lambda e: self.ws_events.append({"tag": tag, "t": self.now(), "ev": "error", "err": str(e)}))

    def anomalies(self) -> dict:
        cons = [c for c in self.console if c["type"] in ("error", "warning") and not is_benign(c["text"])]
        return {
            "console_err_warn": cons,
            "pageerrors": self.pageerrors,
            "failed": [f for f in self.failed if "favicon" not in f["url"]],
            "http_errors": [h for h in self.http_errors if "favicon" not in h["url"]],
        }

    def dump(self) -> dict:
        return {
            "console": self.console,
            "pageerrors": self.pageerrors,
            "failed": self.failed,
            "http_errors": self.http_errors,
            "ws_events": self.ws_events,
            "ws_frames": self.ws_frames,
        }


def text(page, sel: str, timeout: float = 5000) -> str | None:
    """Inner text of the selector or None."""
    try:
        return page.locator(sel).first.inner_text(timeout=timeout)
    except Exception:  # noqa: BLE001
        return None


def jtext(page, sel: str):
    """Parse JSON from the element text."""
    t = text(page, sel)
    try:
        return json.loads(t) if t is not None else None
    except Exception:  # noqa: BLE001
        return t


def wait_text(page, sel: str, expected: str, timeout: float = 15000) -> bool:
    """Wait until the element's text equals expected."""
    deadline = time.time() + timeout / 1000
    while time.time() < deadline:
        if text(page, sel, timeout=500) == expected:
            return True
        page.wait_for_timeout(100)
    return False


def wait_until(page, fn, timeout: float = 15000, step: int = 100):
    """Poll fn() until truthy; return the last value."""
    deadline = time.time() + timeout / 1000
    v = None
    while time.time() < deadline:
        try:
            v = fn()
        except Exception:  # noqa: BLE001
            v = None
        if v:
            return v
        page.wait_for_timeout(step)
    return v


def wait_hydrated(page, timeout: float = 30000) -> bool:
    return wait_text(page, "#hyd-flag", "H:yes", timeout)


def timeline(page) -> list:
    try:
        return page.evaluate("window.__hyd ? window.__hyd.log : []")
    except Exception:  # noqa: BLE001
        return []


def series(tl: list, el_id: str) -> list:
    return [(t, v) for (t, i, v) in tl if i == el_id]


def storage_dump(page) -> dict:
    return page.evaluate(
        """() => ({
            local: Object.fromEntries(Object.keys(localStorage).map(k => [k, (localStorage.getItem(k)||'').length > 200 ? ('<len ' + localStorage.getItem(k).length + '>') : localStorage.getItem(k)])),
            session: Object.fromEntries(Object.keys(sessionStorage).map(k => [k, sessionStorage.getItem(k)])),
            cookie: document.cookie,
        })"""
    )


def parse_sio(frame: dict):
    """Decode a socket.io frame into (kind, payload)."""
    p = frame["p"]
    if not isinstance(p, str):
        return ("bin", None)
    # Strip the socket.io namespace ("42/_event,[...]").
    if len(p) > 2 and p[0] == "4" and p[2:3] == "/":
        comma = p.find(",", 2)
        p = p[:2] + (p[comma + 1:] if comma != -1 else "")
    if p.startswith("42"):
        try:
            return ("event", json.loads(p[2:]))
        except Exception:  # noqa: BLE001
            return ("event-trunc", p[:200])
    if p.startswith("40"):
        try:
            return ("connect", json.loads(p[2:]) if len(p) > 2 else None)
        except Exception:  # noqa: BLE001
            return ("connect-trunc", p[:200])
    if p.startswith("41"):
        return ("disconnect", None)
    if p.startswith("44"):
        return ("connect_error", p[2:200])
    return ("eio", p[:20])


def summarize_frames(frames: list, tag: str | None = None) -> list:
    """Compact summary of socket.io frames: which states/vars each delta carried."""
    out = []
    for f in frames:
        if tag is not None and f["tag"] != tag:
            continue
        kind, payload = parse_sio(f)
        item = {"t": f["t"], "dir": f["dir"], "kind": kind, "len": f["len"]}
        if kind == "event" and isinstance(payload, list) and payload:
            if payload[0] == "event" and len(payload) > 1 and isinstance(payload[1], dict):
                upd = payload[1]
                if "delta" in upd:
                    item["delta"] = {k.split(".")[-1]: sorted(v.keys()) if isinstance(v, dict) else v for k, v in (upd.get("delta") or {}).items()}
                    item["events"] = [e.get("name") for e in upd.get("events") or []]
                elif "name" in upd:
                    item["name"] = upd.get("name")
                    item["payload_keys"] = sorted((upd.get("payload") or {}).keys())
            else:
                item["sio_event"] = payload[0]
        elif kind == "connect" and isinstance(payload, dict):
            ev = payload.get("event") or {}
            item["boot"] = ev.get("name")
            pl = ev.get("payload") or {}
            item["boot_payload_keys"] = sorted(pl.keys())
            if "vars" in pl:
                item["boot_vars"] = {k.split(".")[-1]: (v if len(str(v)) < 60 else f"<len {len(str(v))}>") for k, v in pl["vars"].items()}
            if "hashes" in pl:
                item["n_hashes"] = len(pl["hashes"])
        out.append(item)
    return out


def save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, default=str))
