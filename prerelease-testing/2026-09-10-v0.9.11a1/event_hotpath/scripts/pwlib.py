"""Shared Playwright helpers: capture console/page errors/failed requests, poll helpers."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

CHROMIUM = "/opt/pw-browsers/chromium"
BENIGN = [
    re.compile(r"Hey developer.*HydrateFallback|reactrouter\.com/start/framework/route-module"),
    re.compile(r"\[vite\] (connecting|connected)"),
    re.compile(r"Download the React DevTools"),
]


class Capture:
    def __init__(self, page: Page, label: str = ""):
        self.label = label
        self.console: list[dict] = []
        self.errors: list[str] = []
        self.failed: list[str] = []
        self.responses: list[str] = []
        self.dialogs: list[str] = []
        page.on("dialog", lambda d: (self.dialogs.append(f"{d.type}: {d.message}"[:300]), d.dismiss()))
        page.on("console", lambda m: self.console.append({"type": m.type, "text": m.text}))
        page.on("pageerror", lambda e: self.errors.append(str(e)))
        page.on("requestfailed", lambda r: self.failed.append(f"{r.method} {r.url} {r.failure}"))
        page.on(
            "response",
            lambda r: self.responses.append(f"{r.status} {r.url}") if r.status >= 400 else None,
        )

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
            "dialogs": self.dialogs,
        }


def text_of(page: Page, sel: str) -> str:
    return page.locator(sel).inner_text()


def wait_text(page: Page, sel: str, pred, timeout: float = 10.0, poll: float = 0.05) -> str:
    """Poll until pred(text) is true; return the text (or last seen on timeout)."""
    t_end = time.time() + timeout
    last = ""
    while time.time() < t_end:
        last = text_of(page, sel)
        if pred(last):
            return last
        time.sleep(poll)
    return last


def watch_changes(page: Page, sel: str, duration: float, poll: float = 0.03) -> list[tuple[float, str]]:
    """Record every distinct value of sel over duration seconds, with relative timestamps."""
    t0 = time.time()
    seen: list[tuple[float, str]] = []
    last = None
    while time.time() - t0 < duration:
        t = text_of(page, sel)
        if t != last:
            seen.append((round(time.time() - t0, 3), t))
            last = t
        time.sleep(poll)
    return seen


def launch(pw, headless: bool = True):
    return pw.chromium.launch(executable_path=CHROMIUM, headless=headless)


def dump(path: str | Path, obj) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=1, default=str))
