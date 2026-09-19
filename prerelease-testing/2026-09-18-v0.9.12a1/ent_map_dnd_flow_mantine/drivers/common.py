"""Shared Playwright harness for the ent_map_dnd cluster.

Captures console messages, failed network requests and >=400 responses,
and provides a screenshot helper. Usage:

    with Harness(base_url, out_dir, label) as h:
        page = h.page
        ...
"""

import json
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BENIGN_CONSOLE_SUBSTRINGS = (
    "HydrateFallback",  # React Router dev log
    "[vite] connecting",
    "[vite] connected",
    "React DevTools",
    "Download the React DevTools",
)


class Harness:
    def __init__(self, base_url: str, out_dir: str, label: str, use_proxy_for_external=True):
        self.base_url = base_url.rstrip("/")
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.label = label
        self.console: list[dict] = []
        self.net_fail: list[dict] = []
        self.page_errors: list[str] = []
        self.use_proxy_for_external = use_proxy_for_external
        self._shot_n = 0

    def __enter__(self):
        self._p = sync_playwright().start()
        launch_kwargs = {
            "executable_path": "/opt/pw-browsers/chromium",
            "headless": True,
        }
        proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        if self.use_proxy_for_external and proxy_url:
            launch_kwargs["proxy"] = {
                "server": proxy_url,
                "bypass": "localhost,127.0.0.1",
            }
        self.browser = self._p.chromium.launch(**launch_kwargs)
        self.ctx = self.browser.new_context(
            viewport={"width": 1440, "height": 1000},
            permissions=["geolocation"],
            geolocation={"latitude": 51.6, "longitude": -0.2},
        )
        self.page = self.ctx.new_page()
        self.page.on("console", self._on_console)
        self.page.on("pageerror", lambda e: self.page_errors.append(str(e)))
        self.page.on("requestfailed", self._on_reqfail)
        self.page.on("response", self._on_response)
        return self

    def _on_console(self, msg):
        entry = {"type": msg.type, "text": msg.text, "t": time.time()}
        self.console.append(entry)

    def _on_reqfail(self, req):
        self.net_fail.append(
            {"url": req.url, "failure": req.failure, "method": req.method}
        )

    def _on_response(self, resp):
        if resp.status >= 400:
            self.net_fail.append(
                {"url": resp.url, "status": resp.status, "method": resp.request.method}
            )

    def goto(self, path: str, wait: str = "load"):
        self.page.goto(self.base_url + path, wait_until=wait, timeout=30000)

    def shot(self, name: str):
        self._shot_n += 1
        fn = self.out_dir / f"{self._shot_n:02d}_{name}.png"
        self.page.screenshot(path=str(fn))
        return fn

    def unexpected_console(self):
        out = []
        for c in self.console:
            if c["type"] in ("error", "warning") and not any(
                b in c["text"] for b in BENIGN_CONSOLE_SUBSTRINGS
            ):
                out.append(c)
        return out

    def dump(self):
        data = {
            "label": self.label,
            "console": self.console,
            "unexpected_console": self.unexpected_console(),
            "net_fail": self.net_fail,
            "page_errors": self.page_errors,
        }
        (self.out_dir / "capture.json").write_text(json.dumps(data, indent=2, default=str))
        return data

    def __exit__(self, *exc):
        try:
            self.dump()
        finally:
            self.ctx.close()
            self.browser.close()
            self._p.stop()
        return False
