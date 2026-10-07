"""Playwright harness for the events_vars cluster: console/network/websocket capture + helpers."""

from __future__ import annotations

import json
import re
import time
import traceback
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

CHROMIUM = "/opt/pw-browsers/chromium"
BENIGN = [
    re.compile(r"Hey developer.*HydrateFallback|reactrouter\.com/start/framework/route-module"),
    re.compile(r"\[vite\] (connecting|connected)"),
    re.compile(r"Download the React DevTools"),
]


def is_benign(text: str) -> bool:
    return any(p.search(text) for p in BENIGN)


class Harness:
    """One browser + capture buffers shared by all pages it opens."""

    def __init__(self, base: str, outdir: Path, label: str):
        self.base = base.rstrip("/")
        self.out = outdir
        self.out.mkdir(parents=True, exist_ok=True)
        self.label = label
        self.console: list[dict] = []
        self.page_errors: list[dict] = []
        self.failed: list[dict] = []
        self.http_errors: list[dict] = []
        self.ws_frames: list[dict] = []
        self.results: list[dict] = []
        self.counters: dict[str, int] = {}
        self.t0 = time.time()
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(executable_path=CHROMIUM)

    def now(self) -> float:
        return round(time.time() - self.t0, 3)

    def new_context_page(self, tag: str = "main"):
        ctx = self.browser.new_context(viewport={"width": 1400, "height": 1800})
        page = ctx.new_page()
        self.attach(page, tag)
        return ctx, page

    def _bump(self, key: str) -> int:
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    def attach(self, page: Page, tag: str) -> None:
        # Capped capture: an error storm (e.g. the 0.9.12 wedged event queue) must not exhaust memory.
        def on_console(m):
            if self._bump(f"console:{tag}:{m.type}") <= 150:
                self.console.append({
                    "t": self.now(), "tag": tag, "type": m.type, "text": m.text[:2000],
                    "loc": f"{m.location.get('url', '')}:{m.location.get('lineNumber', '')}",
                    "url": page.url})

        def on_pageerror(e):
            if self._bump(f"pageerror:{tag}") <= 50:
                self.page_errors.append({"t": self.now(), "tag": tag, "error": str(e)[:2000], "url": page.url})

        page.on("console", on_console)
        page.on("pageerror", on_pageerror)
        page.on("requestfailed", lambda r: self.failed.append({"t": self.now(), "tag": tag, "url": r.url, "failure": r.failure}))
        page.on("response", lambda r: r.status >= 400 and self.http_errors.append({"t": self.now(), "tag": tag, "url": r.url, "status": r.status}))

        def frame(direction, p):
            if self._bump(f"ws:{tag}:{direction}") <= 1500:
                self.ws_frames.append({"t": self.now(), "tag": tag, "dir": direction, "data": str(p)[:3000]})

        def on_ws(ws):
            ws.on("framesent", lambda p: frame("sent", p))
            ws.on("framereceived", lambda p: frame("recv", p))
            ws.on("close", lambda w: self.ws_frames.append({"t": self.now(), "tag": tag, "dir": "close", "data": ws.url}))

        page.on("websocket", on_ws)

    def goto(self, page: Page, path: str, settle_ms: int = 300) -> None:
        page.goto(self.base + path, wait_until="networkidle", timeout=120000)
        self.wait_connected(page)
        page.wait_for_timeout(settle_ms)

    def wait_connected(self, page: Page, timeout: float = 60) -> None:
        """Prove a backend round trip: refresh_counts fills #exc-counts (or index token)."""
        deadline = time.time() + timeout
        if page.locator("#exc-refresh").count():
            while time.time() < deadline:
                page.click("#exc-refresh")
                try:
                    page.wait_for_function("() => (document.querySelector('#exc-counts')?.textContent || '').startsWith('backend=')", timeout=3000)
                    return
                except Exception:
                    continue
            raise TimeoutError("backend round trip never completed")
        page.wait_for_function("() => (document.querySelector('#token')?.textContent || '').length > 10", timeout=timeout * 1000)

    @staticmethod
    def text(page: Page, el_id: str) -> str:
        loc = page.locator(f"#{el_id}")
        if not loc.count():
            return "<missing>"
        return loc.first.inner_text()

    @staticmethod
    def spans(page: Page, el_id: str) -> list[str]:
        return page.eval_on_selector_all(f"#{el_id} span", "els => els.map(e => e.textContent)")

    def wait_text(self, page: Page, el_id: str, expected: str, timeout: float = 10) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.text(page, el_id) == expected:
                return True
            page.wait_for_timeout(100)
        return False

    def wait_pred(self, page: Page, el_id: str, pred, timeout: float = 10) -> str:
        deadline = time.time() + timeout
        val = self.text(page, el_id)
        while time.time() < deadline:
            val = self.text(page, el_id)
            if pred(val):
                return val
            page.wait_for_timeout(100)
        return val

    def timeline(self, page: Page, ids: list[str], duration: float, interval_ms: int = 100) -> dict[str, list]:
        """Record (t, text) whenever any watched element's text changes."""
        tl = {i: [] for i in ids}
        last = {i: None for i in ids}
        start = time.time()
        while time.time() - start < duration:
            for i in ids:
                v = self.text(page, i)
                if v != last[i]:
                    tl[i].append((round(time.time() - start, 2), v))
                    last[i] = v
            page.wait_for_timeout(interval_ms)
        return tl

    def exc_count(self, page: Page) -> int:
        t = self.text(page, "exc-count")
        try:
            return int(t)
        except ValueError:
            return -1

    def counts(self, page: Page) -> str:
        page.click("#exc-refresh")
        page.wait_for_timeout(400)
        return self.text(page, "exc-counts")

    def shot(self, page: Page, name: str) -> str:
        p = self.out / f"{self.label}_{name}.png"
        page.screenshot(path=str(p), full_page=True)
        return str(p)

    def record(self, name: str, status: str, details: dict | str) -> None:
        self.results.append({"name": name, "status": status, "details": details, "t": self.now()})
        print(f"[{status.upper():7}] {name}: {json.dumps(details)[:900]}", flush=True)

    def run(self, name: str, fn, *args) -> None:
        mark_c, mark_e = len(self.console), len(self.page_errors)
        try:
            fn(self, *args)
        except Exception as e:
            self.record(name, "error", {"exception": f"{type(e).__name__}: {e}", "tb": traceback.format_exc()[-1500:]})
        new_console = [c for c in self.console[mark_c:] if not is_benign(c["text"]) and c["type"] in ("error", "warning")]
        if new_console or self.page_errors[mark_e:]:
            self.record(name + " [console]", "anomaly", {"console": new_console[:10], "page_errors": self.page_errors[mark_e:][:5]})

    def dump(self, extra: dict | None = None) -> Path:
        report = {
            "label": self.label, "base": self.base, "results": self.results,
            "console_non_benign": [c for c in self.console if not is_benign(c["text"])],
            "page_errors": self.page_errors, "failed_requests": self.failed,
            "http_errors": self.http_errors, "counters": self.counters, "extra": extra or {},
        }
        p = self.out / f"{self.label}_report.json"
        p.write_text(json.dumps(report, indent=1, default=str))
        (self.out / f"{self.label}_wsframes.json").write_text(json.dumps(self.ws_frames, indent=0, default=str))
        return p

    def close(self) -> None:
        try:
            self.browser.close()
        finally:
            self._pw.stop()
