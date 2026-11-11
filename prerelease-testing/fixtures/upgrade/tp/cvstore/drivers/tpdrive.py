"""Shared Playwright helpers for the thirdparty cluster drivers.

Run drivers with the driver venv:
  NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python <driver>.py ...
"""

from __future__ import annotations

import json
import re
import time
import traceback
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import BrowserContext, Page, sync_playwright

CHROMIUM = "/opt/pw-browsers/chromium"
BENIGN_CONSOLE = [
    re.compile(r"Hey developer.*HydrateFallback|reactrouter\.com/start/framework/route-module"),
    re.compile(r"\[vite\] (connecting|connected)"),
    re.compile(r"Download the React DevTools"),
]


def is_benign(text: str) -> bool:
    return any(p.search(text) for p in BENIGN_CONSOLE)


class Capture:
    """Collects console, page errors, failed requests, bad responses and ws frames."""

    def __init__(self, ws_frames: bool = False):
        self.console: list[dict] = []
        self.page_errors: list[dict] = []
        self.failed_requests: list[dict] = []
        self.bad_responses: list[dict] = []
        self.ws: list[dict] = []
        self.ws_frames = ws_frames
        self.checks: list[dict] = []
        self.label = "start"

    def attach(self, page: Page, name: str = "page") -> Page:
        page.on("console", lambda m: self.console.append({"where": self.label, "page": name, "type": m.type, "text": m.text[:2000], "benign": is_benign(m.text)}))
        page.on("pageerror", lambda e: self.page_errors.append({"where": self.label, "page": name, "error": str(e)[:3000]}))
        page.on("requestfailed", lambda r: self.failed_requests.append({"where": self.label, "page": name, "url": r.url, "failure": r.failure}))
        page.on("response", lambda r: r.status >= 400 and self.bad_responses.append({"where": self.label, "page": name, "url": r.url, "status": r.status}))
        if self.ws_frames:
            def on_ws(ws):
                ws.on("framesent", lambda p: self.ws.append({"where": self.label, "dir": "sent", "data": str(p)[:1500]}))
                ws.on("framereceived", lambda p: self.ws.append({"where": self.label, "dir": "recv", "data": str(p)[:1500]}))
            page.on("websocket", on_ws)
        return page

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        self.checks.append({"name": name, "ok": bool(ok), "detail": str(detail)[:2000]})
        print(("PASS " if ok else "FAIL ") + name + (f" :: {detail}" if detail else ""), flush=True)
        return ok

    def anomalies(self) -> dict:
        return {
            "console_nonbenign": [c for c in self.console if not c["benign"] and c["type"] in ("error", "warning")],
            "page_errors": self.page_errors,
            "failed_requests": [r for r in self.failed_requests if "favicon" not in r["url"]],
            "bad_responses": [r for r in self.bad_responses if "favicon" not in r["url"]],
        }

    def dump(self, path: str | Path, extra: dict | None = None) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        data = {
            "checks": self.checks,
            "anomalies": self.anomalies(),
            "console_all": self.console,
            "failed_requests_all": self.failed_requests,
            "bad_responses_all": self.bad_responses,
            "ws": self.ws,
            **(extra or {}),
        }
        Path(path).write_text(json.dumps(data, indent=1, default=str))
        n_fail = sum(1 for c in self.checks if not c["ok"])
        an = self.anomalies()
        print(f"SUMMARY checks={len(self.checks)} failed={n_fail} console_err/warn={len(an['console_nonbenign'])} pageerrors={len(an['page_errors'])} failedreq={len(an['failed_requests'])} badresp={len(an['bad_responses'])}", flush=True)
        for k, v in an.items():
            for item in v[:15]:
                print(f"  ANOMALY {k}: {json.dumps(item, default=str)[:600]}", flush=True)


@contextmanager
def browser(headless: bool = True, args: list[str] | None = None):
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROMIUM, headless=headless, args=args or [])
        try:
            yield b
        finally:
            b.close()


def wait_text(page: Page, selector: str, pattern: str | re.Pattern, timeout: float = 15.0) -> str:
    """Wait until the text of selector matches pattern (regex); return the text (or last seen)."""
    rx = re.compile(pattern) if isinstance(pattern, str) else pattern
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            loc = page.locator(selector)
            if loc.count() > 0:
                last = loc.first.inner_text(timeout=1000)
                if rx.search(last):
                    return last
        except Exception as e:  # noqa: BLE001
            last = f"<err {type(e).__name__}: {e}>"
        page.wait_for_timeout(200)  # pumps the Playwright event loop (time.sleep does not)
    return f"TIMEOUT(last={last!r})"


def wait_url(page: Page, pattern: str, timeout: float = 15.0) -> str:
    rx = re.compile(pattern)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if rx.search(page.url):
            return page.url
        page.wait_for_timeout(200)  # pumps the Playwright event loop (time.sleep does not)
    return f"TIMEOUT(url={page.url})"


def safe(cap: Capture, name: str, fn):
    """Run a step; record an exception as a failed check instead of aborting."""
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        cap.check(name, False, f"exception: {type(e).__name__}: {e}\n{traceback.format_exc()[-1500:]}")
        return None
