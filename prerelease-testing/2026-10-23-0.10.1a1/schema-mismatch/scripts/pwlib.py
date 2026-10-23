"""Shared Playwright capture helpers for the schema-mismatch cluster.

Run with the driver venv:
  NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python <script>
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

CHROMIUM = "/opt/pw-browsers/chromium"
BENIGN = [
    re.compile(r"Hey developer.*HydrateFallback|reactrouter\.com/start/framework/route-module"),
    re.compile(r"\[vite\] (connecting|connected)"),
    re.compile(r"Download the React DevTools"),
]


class Capture:
    """Collects console messages, page errors, requests, failures and websocket frames."""

    def __init__(self, page):
        self.console: list[dict] = []
        self.pageerrors: list[str] = []
        self.requests: list[dict] = []
        self.failed: list[dict] = []
        self.responses_bad: list[dict] = []
        self.ws: list[dict] = []
        self.loads: list[dict] = []
        self.t0 = time.time()
        page.on("console", lambda m: self.console.append({"t": self.rel(), "type": m.type, "text": m.text}))
        page.on("pageerror", lambda e: self.pageerrors.append(f"{self.rel():.2f} {e}"))
        page.on("request", lambda r: self.requests.append({"t": self.rel(), "method": r.method, "url": r.url}))
        page.on("requestfailed", lambda r: self.failed.append({"t": self.rel(), "url": r.url, "err": r.failure}))
        page.on("response", lambda r: r.status >= 400 and self.responses_bad.append({"t": self.rel(), "status": r.status, "url": r.url}))
        page.on("load", lambda: self.loads.append({"t": self.rel(), "url": page.url}))

        def on_ws(ws):
            self.ws.append({"t": self.rel(), "event": "open", "url": ws.url})
            def frame(direction):
                def _rec(f):
                    payload = f if isinstance(f, (str, bytes)) else getattr(f, "payload", f)
                    payload = payload if isinstance(payload, str) else repr(payload)
                    self.ws.append({"t": self.rel(), "event": direction, "payload": payload[:600]})
                return _rec

            ws.on("framesent", frame("sent"))
            ws.on("framereceived", frame("recv"))
            ws.on("close", lambda: self.ws.append({"t": self.rel(), "event": "close", "url": ws.url}))
            ws.on("socketerror", lambda e: self.ws.append({"t": self.rel(), "event": "error", "err": str(e)}))

        page.on("websocket", on_ws)

    def rel(self) -> float:
        return round(time.time() - self.t0, 3)

    def anomalies(self) -> list[str]:
        out = []
        for m in self.console:
            if m["type"] in ("error", "warning") and not any(b.search(m["text"]) for b in BENIGN):
                out.append(f"console.{m['type']}: {m['text'][:300]}")
        out += [f"pageerror: {e}" for e in self.pageerrors]
        out += [f"requestfailed: {f['url']} {f['err']}" for f in self.failed]
        out += [f"http {r['status']}: {r['url']}" for r in self.responses_bad]
        return out

    def dump(self, path: str | Path, **extra):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps({
            "console": self.console, "pageerrors": self.pageerrors, "failed": self.failed,
            "responses_bad": self.responses_bad, "ws": self.ws, "loads": self.loads,
            "n_requests": len(self.requests), "anomalies": self.anomalies(), **extra,
        }, indent=1, default=str))


def browser(p):
    return p.chromium.launch(executable_path=CHROMIUM)


__all__ = ["Capture", "browser", "sync_playwright"]
