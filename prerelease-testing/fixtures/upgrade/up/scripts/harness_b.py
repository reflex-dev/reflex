"""Shared Playwright capture harness for the upgrades_a drivers.

Every driver records: per-check results, browser console (all types), page errors,
failed requests, >=400 responses, reflex websocket frames (in/out, trimmed) and
screenshots. `Run.finish()` writes <out>/<tag>.json and prints a summary in which
known-benign noise (see AGENT_BRIEF) is filtered from the "unexpected" lists.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

CHROMIUM = "/opt/pw-browsers/chromium"
WS_CAP = int(os.environ.get("QA_WS_CAP", "3000"))  # max chars kept per websocket frame

BENIGN_CONSOLE = [
    re.compile(r"Hey developer.*HydrateFallback|reactrouter\.com/start/framework/route-module"),
    re.compile(r"\[vite\] (connecting|connected)"),
    re.compile(r"Download the React DevTools"),
]
# Requests that fail for environment reasons (agent proxy / no favicon).
BENIGN_URL = [re.compile(r"fonts\.(googleapis|gstatic)\.com"), re.compile(r"/favicon\.ico$")]


def is_benign_console(text: str) -> bool:
    return any(p.search(text) for p in BENIGN_CONSOLE)


def is_benign_url(url: str) -> bool:
    return any(p.search(url) for p in BENIGN_URL)


class Run:
    def __init__(self, tag: str, outdir: str | Path):
        self.tag = tag
        self.out = Path(outdir)
        self.out.mkdir(parents=True, exist_ok=True)
        self.results: list[dict] = []
        self.console: list[dict] = []
        self.page_errors: list[dict] = []
        self.bad: list[dict] = []
        self.ws: list[dict] = []
        self.t0 = time.time()
        self.notes: dict = {}
        self.expected_bad: list = []  # callables(entry)->bool for failures the flow causes on purpose

    def _t(self) -> float:
        return round(time.time() - self.t0, 3)

    def attach(self, page, label: str = "main") -> None:
        page.on("console", lambda m: self.console.append(
            {"page": label, "t": self._t(), "type": m.type, "text": m.text}))
        page.on("pageerror", lambda e: self.page_errors.append(
            {"page": label, "t": self._t(), "error": str(e)}))
        page.on("requestfailed", lambda r: self.bad.append(
            {"page": label, "t": self._t(), "url": r.url, "failure": r.failure}))
        page.on("response", lambda r: self.bad.append(
            {"page": label, "t": self._t(), "url": r.url, "status": r.status})
            if r.status >= 400 else None)
        page.on("websocket", lambda ws: self._ws(ws, label))

    def _ws(self, ws, label: str) -> None:
        if "/_event" not in ws.url:
            return  # skip vite HMR socket
        self.ws.append({"page": label, "t": self._t(), "dir": "open", "payload": ws.url})

        def rec(direction):
            def _f(payload):
                text = payload if isinstance(payload, str) else f"<{len(payload)} bytes>"
                self.ws.append({"page": label, "t": self._t(), "dir": direction,
                                "len": len(text), "payload": text[:WS_CAP]})
            return _f

        ws.on("framereceived", rec("in"))
        ws.on("framesent", rec("out"))
        ws.on("close", lambda *_: self.ws.append(
            {"page": label, "t": self._t(), "dir": "close", "payload": ""}))

    def check(self, name: str, status, detail="") -> bool:
        if isinstance(status, bool):
            status = "pass" if status else "fail"
        self.results.append({"name": name, "status": status, "detail": str(detail)[:1500], "t": self._t()})
        print(f"[{status.upper():7}] {name}: {str(detail)[:400]}", flush=True)
        return status == "pass"

    def shot(self, page, name: str) -> None:
        try:
            page.screenshot(path=str(self.out / f"{self.tag}_{name}.jpg"), type="jpeg", quality=55)
        except Exception as e:  # noqa: BLE001
            print("screenshot failed", name, e)

    def unexpected_console(self) -> list[dict]:
        return [m for m in self.console if m["type"] in ("error", "warning")
                and not is_benign_console(m["text"])]

    def unexpected_bad(self) -> list[dict]:
        return [b for b in self.bad if not is_benign_url(b["url"]) and not any(f(b) for f in self.expected_bad)]

    def finish(self) -> int:
        uc, ub = self.unexpected_console(), self.unexpected_bad()
        self.check("console: no unexpected errors/warnings + no page errors",
                   "pass" if not uc and not self.page_errors else "anomaly",
                   json.dumps(uc + self.page_errors)[:1500])
        self.check("network: no unexpected failed/4xx/5xx requests",
                   "pass" if not ub else "anomaly", json.dumps(ub)[:1500])
        data = {"tag": self.tag, "results": self.results, "console": self.console,
                "page_errors": self.page_errors, "bad_requests": self.bad,
                "ws_frames": self.ws, "notes": self.notes}
        (self.out / f"{self.tag}.json").write_text(json.dumps(data, indent=1, default=str))
        n = {s: sum(1 for r in self.results if r["status"] == s) for s in ("pass", "fail", "anomaly", "skipped")}
        print(f"\n== {self.tag}: {n}  console_total={len(self.console)} unexpected_console={len(uc)} "
              f"page_errors={len(self.page_errors)} bad_requests={len(self.bad)} (unexpected {len(ub)}) "
              f"ws_frames={len(self.ws)}")
        for m in uc:
            print("  UNEXPECTED CONSOLE:", m["type"], m["text"][:300])
        for e in self.page_errors:
            print("  PAGE ERROR:", e["error"][:300])
        for b in ub:
            print("  BAD REQUEST:", b)
        return 0 if n["fail"] == 0 else 1


def wait_for(fn, timeout: float = 10.0, interval: float = 0.25):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            last = fn()
            if last:
                return last
        except Exception:  # noqa: BLE001
            pass
        time.sleep(interval)
    return None


def guard_driver_python() -> None:
    assert ("/envs/" + __import__("os").environ.get("DRIVER", "driver") + "/") in sys.executable, sys.executable
