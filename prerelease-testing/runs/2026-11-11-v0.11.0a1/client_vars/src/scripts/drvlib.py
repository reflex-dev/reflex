"""Shared Playwright helpers for the client_vars cluster (driver venv)."""
import json
import os
import sys
import time

import playwright

assert "/envs/driver/" in playwright.__file__, playwright.__file__
from playwright.sync_api import sync_playwright

BENIGN = (
    "Hey developer",
    "[vite]",
    "Download the React DevTools",
    "favicon.ico",
)


class Run:
    def __init__(self, base, label, outdir):
        self.base = base.rstrip("/")
        self.label = label
        self.outdir = outdir
        os.makedirs(outdir, exist_ok=True)
        self.checks = []
        self.console = []
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        self.ctx = self.browser.new_context()

    def new_page(self, tag="p"):
        page = self.ctx.new_page()
        self.watch(page, tag)
        return page

    def watch(self, page, tag):
        page.on("console", lambda m: self.console.append({"tab": tag, "type": m.type, "text": m.text[:1500]}))
        page.on("pageerror", lambda e: self.console.append({"tab": tag, "type": "pageerror", "text": str(e)[:1500]}))
        page.on("requestfailed", lambda r: self.console.append({"tab": tag, "type": "requestfailed", "text": f"{r.method} {r.url} {r.failure}"}))
        page.on("response", lambda r: r.status >= 400 and self.console.append({"tab": tag, "type": "http", "text": f"{r.status} {r.url}"}))

    def goto(self, page, path, wait_hyd=True):
        page.goto(self.base + path)
        if wait_hyd:
            page.wait_for_function("document.querySelector('#hyd') && document.querySelector('#hyd').textContent === 'hydrated'", timeout=60000)

    def check(self, name, ok, detail=""):
        self.checks.append({"name": name, "ok": bool(ok), "detail": str(detail)[:600]})
        print(("PASS " if ok else "FAIL ") + name + (f" :: {detail}" if detail != "" else ""), flush=True)

    def expect_text(self, page, sel, want, name=None, timeout=5000):
        name = name or f"{sel} == {want!r}"
        end = time.time() + timeout / 1000
        got = None
        while time.time() < end:
            try:
                got = page.locator(sel).first.text_content(timeout=1000)
            except Exception as e:  # noqa: BLE001
                got = f"<{type(e).__name__}>"
            if got == want:
                break
            time.sleep(0.05)
        self.check(name, got == want, f"got {got!r}")
        return got

    def noise(self):
        return [c for c in self.console if c["type"] in ("error", "warning", "pageerror", "requestfailed", "http") and not any(b in c["text"] for b in BENIGN)]

    def finish(self):
        noise = self.noise()
        print(f"--- console noise ({len(noise)}) ---")
        seen = {}
        for c in noise:
            k = (c["type"], c["text"][:300])
            seen[k] = seen.get(k, 0) + 1
        for (t, text), n in seen.items():
            print(f"  x{n} [{t}] {text}")
        out = {"label": self.label, "checks": self.checks, "console": self.console}
        with open(os.path.join(self.outdir, f"{self.label}.json"), "w") as f:
            json.dump(out, f, indent=1)
        fails = [c for c in self.checks if not c["ok"]]
        print(f"SUMMARY {self.label}: {len(self.checks) - len(fails)}/{len(self.checks)} pass; console noise {len(noise)}")
        self.browser.close()
        self.pw.stop()
        return fails
