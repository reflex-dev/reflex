"""Shared Playwright helpers for the state-events cluster tests.

Run with the driver venv:  NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python <script> ...
"""

from __future__ import annotations

import json
import re
import sys
import time
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import sync_playwright

CHROMIUM = "/opt/pw-browsers/chromium"
BENIGN = [
    re.compile(r"Hey developer.*HydrateFallback|reactrouter\.com/start/framework/route-module"),
    re.compile(r"\[vite\] (connecting|connected)"),
    re.compile(r"Download the React DevTools"),
]


class Capture:
    def __init__(self):
        self.console: list[dict] = []
        self.page_errors: list[str] = []
        self.failed: list[dict] = []
        self.bad_status: list[dict] = []

    def attach(self, page):
        page.on("console", lambda m: self.console.append({"type": m.type, "text": m.text}))
        page.on("pageerror", lambda e: self.page_errors.append(str(e)))
        page.on("requestfailed", lambda r: self.failed.append({"url": r.url, "failure": str(r.failure)}))
        page.on(
            "response",
            lambda r: self.bad_status.append({"url": r.url, "status": r.status}) if r.status >= 400 else None,
        )

    def problems(self) -> list[dict]:
        return [
            m
            for m in self.console
            if m["type"] in ("error", "warning") and not any(p.search(m["text"]) for p in BENIGN)
        ]

    def summary(self) -> dict:
        return {
            "console_problems": self.problems(),
            "console_all": [m for m in self.console if not any(p.search(m["text"]) for p in BENIGN)],
            "page_errors": self.page_errors,
            "failed_requests": self.failed,
            "http_4xx_5xx": self.bad_status,
        }


@contextmanager
def browser(headless: bool = True):
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROMIUM, headless=headless)
        try:
            yield b
        finally:
            b.close()


def new_page(browser_, cap: Capture | None = None):
    ctx = browser_.new_context()
    page = ctx.new_page()
    if cap is not None:
        cap.attach(page)
    return ctx, page


def text(page, selector: str) -> str:
    return page.inner_text(selector)


def wait_text(page, selector: str, expected: str, timeout: float = 10.0) -> str:
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        last = page.inner_text(selector)
        if last.strip() == expected.strip():
            return last
        page.wait_for_timeout(100)
    raise AssertionError(f"{selector}: expected {expected!r}, last saw {last!r}")


def wait_until(fn, timeout: float = 10.0, interval: float = 0.1, what: str = "condition"):
    deadline = time.time() + timeout
    while time.time() < deadline:
        v = fn()
        if v:
            return v
        time.sleep(interval)
    raise AssertionError(f"timeout waiting for {what}")


def write_report(path: str | Path, data: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, default=str))


def read_markers(markers_dir: Path) -> dict[str, int]:
    out = {}
    for f in sorted(markers_dir.glob("*")):
        out[f.name] = len(f.read_text().splitlines())
    return out


def clear_markers(markers_dir: Path) -> None:
    for f in markers_dir.glob("*"):
        f.unlink()


def check(name: str, cond: bool, detail: str, results: list[dict]) -> None:
    results.append({"name": name, "status": "pass" if cond else "fail", "details": detail})
    print(("PASS " if cond else "FAIL ") + name + " :: " + detail, flush=True)


def finish(results: list[dict], cap: Capture, report_path: str) -> int:
    s = cap.summary()
    report = {"results": results, **s}
    write_report(report_path, report)
    for m in s["console_problems"]:
        print(f"  [console {m['type']}] {m['text'][:400]}")
    for e in s["page_errors"]:
        print(f"  PAGE ERROR: {e[:400]}")
    for f in s["failed_requests"]:
        print(f"  REQUEST FAILED: {f}")
    for b in s["http_4xx_5xx"]:
        print(f"  HTTP {b['status']}: {b['url']}")
    failed = [r for r in results if r["status"] == "fail"]
    print(f"REPORT -> {report_path}; {len(failed)} failed of {len(results)}")
    return 1 if failed else 0
