"""Shared Playwright helpers: capture console, page errors, failed requests."""
import json
import re
import sys
from contextlib import contextmanager

from playwright.sync_api import sync_playwright

BENIGN = [re.compile(p) for p in [r"Hey developer.*HydrateFallback|route-module", r"\[vite\] (connecting|connected)", r"Download the React DevTools"]]
SHOTS = "/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/apps/db_models/shots"


class Cap:
    def __init__(self):
        self.console = []
        self.errors = []
        self.failed = []

    def attach(self, page, tag=""):
        page.on("console", lambda m: None if any(b.search(m.text) for b in BENIGN) else self.console.append(f"{tag}[{m.type}] {m.text[:400]}"))
        page.on("pageerror", lambda e: self.errors.append(f"{tag}{e}"[:600]))
        page.on("requestfailed", lambda r: self.failed.append(f"{tag}FAILED {r.url} {r.failure}"))
        page.on("response", lambda r: self.failed.append(f"{tag}HTTP {r.status} {r.url}") if r.status >= 400 else None)

    def report(self):
        print("CONSOLE:", json.dumps(self.console, indent=1))
        print("PAGEERRORS:", json.dumps(self.errors, indent=1))
        print("FAILED:", json.dumps(self.failed, indent=1))


@contextmanager
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        try:
            yield b
        finally:
            b.close()


def text(page, sel, timeout=15000):
    page.wait_for_selector(sel, timeout=timeout)
    return page.inner_text(sel)


def wait_text(page, sel, needle, timeout=15000):
    page.wait_for_function(
        "([s, n]) => { const e = document.querySelector(s); return e && e.innerText.includes(n); }",
        arg=[sel, needle], timeout=timeout,
    )


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f" :: {detail}" if detail else ""))
    return cond
