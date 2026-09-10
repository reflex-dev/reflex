"""Shared Playwright helpers: console/page-error/failed-request capture, websocket frame capture,
polling helpers, and a tiny result recorder. Run with $SB/envs/driver/bin/python."""
from __future__ import annotations

import json
import re
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, sync_playwright  # noqa: F401

CHROMIUM = "/opt/pw-browsers/chromium"
BENIGN = [
    re.compile(r"Hey developer.*HydrateFallback|reactrouter\.com/start/framework/route-module"),
    re.compile(r"\[vite\] (connecting|connected)"),
    re.compile(r"Download the React DevTools"),
]
RESULTS: list[dict] = []
_SIO_RE = re.compile(r"^42(?:/[^,]*,)?(\[.*)$", re.S)


def _sio_event(data: str):
    """Parse a socket.io EVENT frame ('42/_event,["event", {...}]') -> the payload dict, or None."""
    m = _SIO_RE.match(data)
    if not m:
        return None
    try:
        arr = json.loads(m.group(1))
    except Exception:  # noqa: BLE001
        return None
    if isinstance(arr, list) and len(arr) == 2 and arr[0] == "event":
        payload = arr[1]
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:  # noqa: BLE001
                pass
        return payload
    return None


def rec(name: str, status: str, details: str, **extra) -> None:
    RESULTS.append({"name": name, "status": status, "details": details, **extra})
    print(f"[{status.upper():7}] {name}: {details}", flush=True)


class Capture:
    """Attach to a page; records console, page errors, failed requests, 4xx/5xx and websocket frames."""

    def __init__(self, page: Page, label: str = ""):
        self.label = label
        self.console: list[dict] = []
        self.errors: list[str] = []
        self.failed: list[str] = []
        self.responses: list[str] = []
        self.ws_frames: list[dict] = []  # {"t": rel_time, "dir": "recv"/"send", "data": str}
        self.t0 = time.time()
        page.on("console", lambda m: self.console.append({"type": m.type, "text": m.text}))
        page.on("pageerror", lambda e: self.errors.append(str(e)))
        page.on("requestfailed", lambda r: self.failed.append(f"{r.method} {r.url} {r.failure}"))
        page.on(
            "response",
            lambda r: self.responses.append(f"{r.status} {r.url}") if r.status >= 400 else None,
        )
        page.on("websocket", self._on_ws)

    def _on_ws(self, ws):
        ws.on("framereceived", lambda payload: self.ws_frames.append(
            {"t": round(time.time() - self.t0, 3), "dir": "recv", "data": payload if isinstance(payload, str) else repr(payload)}))
        ws.on("framesent", lambda payload: self.ws_frames.append(
            {"t": round(time.time() - self.t0, 3), "dir": "send", "data": payload if isinstance(payload, str) else repr(payload)}))
        self.ws_frames.append({"t": round(time.time() - self.t0, 3), "dir": "open", "data": ws.url})
        ws.on("close", lambda _ws: self.ws_frames.append({"t": round(time.time() - self.t0, 3), "dir": "close", "data": ws.url}))

    def deltas(self, since_index: int = 0) -> list[dict]:
        """Parse received socket.io 'event' frames into their update payloads (delta/events)."""
        out = []
        for f in self.ws_frames[since_index:]:
            if f["dir"] != "recv":
                continue
            arr = _sio_event(f["data"])
            if arr is not None:
                out.append({"t": f["t"], "update": arr})
        return out

    def sent_events(self, since_index: int = 0) -> list[dict]:
        out = []
        for f in self.ws_frames[since_index:]:
            if f["dir"] != "send":
                continue
            arr = _sio_event(f["data"])
            if arr is not None:
                out.append({"t": f["t"], "event": arr})
        return out

    def anomalies(self) -> dict:
        bad_console = [
            c for c in self.console
            if c["type"] in ("error", "warning") and not any(b.search(c["text"]) for b in BENIGN)
        ]
        return {
            "label": self.label,
            "console_err_warn": bad_console,
            "page_errors": self.errors,
            "failed_requests": self.failed,
            "http_4xx_5xx": self.responses,
        }


def hydrate_deltas(deltas: list[dict], state_name: str = "reflex___state____state") -> list[dict]:
    """Deltas produced by State.hydrate: root delta with is_hydrated=False AND the full router var.

    (on_load_internal also emits is_hydrated=False, but only that one key, so it is excluded.)
    """
    out = []
    for d in deltas:
        if not isinstance(d["update"], dict):
            continue
        root = (d["update"].get("delta") or {}).get(state_name, {})
        if root.get("is_hydrated_rx_state_") is False and "router_rx_state_" in root:
            out.append(d)
    return out


def text_of(page: Page, sel: str) -> str:
    return page.locator(sel).first.inner_text()


def wait_text(page: Page, sel: str, pred, timeout: float = 10.0, poll: float = 0.05) -> str:
    """Poll until pred(text) is true; return the text (or last seen on timeout)."""
    t_end = time.time() + timeout
    last = ""
    while time.time() < t_end:
        try:
            last = text_of(page, sel)
        except Exception:  # noqa: BLE001
            last = "<missing>"
        if pred(last):
            return last
        time.sleep(poll)
    return last


def http_json(url: str, timeout: float = 15.0):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def launch(pw, headless: bool = True):
    return pw.chromium.launch(executable_path=CHROMIUM, headless=headless)


def dump(path: str | Path, obj) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=1, default=str))


def token_of(page: Page) -> str:
    return page.evaluate("() => window.sessionStorage.getItem('token')")


def snapshot(page: Page, ids: list[str]) -> dict:
    out = {}
    for i in ids:
        try:
            out[i] = text_of(page, f"#{i}")
        except Exception as ex:  # noqa: BLE001
            out[i] = f"<err {type(ex).__name__}>"
    return out
