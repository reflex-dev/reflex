"""Shared Playwright plumbing for the traversal / quiz drivers (console, page errors,
failed + 4xx/5xx responses, results.json, screenshots)."""

import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

CHROMIUM = "/opt/pw-browsers/chromium"

BENIGN = ("HydrateFallback", "React DevTools", "[vite] connecting", "[vite] connected")


class Run:
    def __init__(self, art_dir: str, label: str):
        self.art = Path(art_dir)
        self.art.mkdir(parents=True, exist_ok=True)
        self.label = label
        self.results = []
        self.console = []
        self.bad = []
        self.page_errors = []
        self._pw = None
        self.browser = None

    def __enter__(self):
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(executable_path=CHROMIUM)
        return self

    def __exit__(self, *exc):
        try:
            self.browser.close()
        finally:
            self._pw.stop()
        self.finish()

    def new_page(self, tag="", color_scheme=None):
        ctx = self.browser.new_context(color_scheme=color_scheme) if color_scheme else self.browser.new_context()
        page = ctx.new_page()
        prefix = f"[{tag}] " if tag else ""
        page.on("console", lambda m: self.console.append({"type": m.type, "text": prefix + m.text}))
        page.on("pageerror", lambda e: self.page_errors.append(prefix + str(e)))
        page.on(
            "response",
            lambda r: self.bad.append({"url": r.url, "status": r.status}) if r.status >= 400 else None,
        )
        page.on(
            "requestfailed",
            lambda r: self.bad.append({"url": r.url, "status": "FAILED:" + str(r.failure)}),
        )
        return ctx, page

    def record(self, name, status, details=""):
        self.results.append({"name": name, "status": status, "details": details})
        print(f"[{status.upper()}] {name}: {details}", flush=True)

    def shot(self, page, name, full_page=False):
        page.screenshot(path=str(self.art / name), full_page=full_page)

    def unexpected_console(self):
        return [
            m for m in self.console
            if m["type"] in ("error", "warning") and not any(b in m["text"] for b in BENIGN)
        ]

    def finish(self):
        (self.art / "console.json").write_text(json.dumps(self.console, indent=2, ensure_ascii=False))
        (self.art / "bad_responses.json").write_text(json.dumps(self.bad, indent=2))
        (self.art / "page_errors.json").write_text(json.dumps(self.page_errors, indent=2))
        (self.art / "results.json").write_text(json.dumps(self.results, indent=2, ensure_ascii=False))
        print("\nUNEXPECTED CONSOLE:", json.dumps(self.unexpected_console(), indent=2, ensure_ascii=False))
        print("ALL CONSOLE TYPES:", json.dumps(sorted({m["type"] for m in self.console})))
        print("BAD RESPONSES:", json.dumps(self.bad, indent=2))
        print("PAGE ERRORS:", json.dumps(self.page_errors, indent=2))
        print("SUMMARY:", json.dumps({r["name"]: r["status"] for r in self.results}, ensure_ascii=False))


def wait_for(pred, timeout=15.0, step=0.2):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if pred():
                return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(step)
    try:
        return bool(pred())
    except Exception:  # noqa: BLE001
        return False
