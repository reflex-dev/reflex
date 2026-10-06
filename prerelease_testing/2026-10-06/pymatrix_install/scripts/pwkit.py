"""Shared Playwright capture helpers for the pymatrix_install drivers (run with the driver venv)."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from playwright.sync_api import Page

CHROMIUM = "/opt/pw-browsers/chromium"
BENIGN = [
    re.compile(r"Hey developer.*HydrateFallback|reactrouter\.com/start/framework/route-module"),
    re.compile(r"\[vite\] (connecting|connected)"),
    re.compile(r"Download the React DevTools"),
]


class Sink:
    """Collects console, page errors, failed requests, bad responses and ws frames."""

    def __init__(self) -> None:
        self.console: list[dict] = []
        self.page_errors: list[str] = []
        self.failed_requests: list[str] = []
        self.bad_responses: list[str] = []
        self.ws: list[dict] = []
        self.checks: list[dict] = []

    def attach(self, page: Page, tag: str = "") -> None:
        page.on("console", lambda m: self.console.append({"tab": tag, "type": m.type, "text": m.text[:800]}))
        page.on("pageerror", lambda e: self.page_errors.append(f"{tag} {e}"[:1500]))
        page.on(
            "requestfailed",
            lambda r: self.failed_requests.append(f"{tag} {r.method} {r.url} {r.failure}"),
        )
        page.on(
            "response",
            lambda r: self.bad_responses.append(f"{tag} {r.status} {r.url}") if r.status >= 400 else None,
        )

        def on_ws(ws):
            entry = {"tab": tag, "url": ws.url, "sent": 0, "recv": 0, "first_recv": [], "closed": False}
            self.ws.append(entry)

            def recv(payload):
                entry["recv"] += 1
                if len(entry["first_recv"]) < 4:
                    entry["first_recv"].append(str(payload)[:300])

            ws.on("framereceived", recv)
            ws.on("framesent", lambda p: entry.__setitem__("sent", entry["sent"] + 1))
            ws.on("close", lambda w: entry.__setitem__("closed", True))

        page.on("websocket", on_ws)

    def check(self, name: str, fn) -> bool:
        t0 = time.time()
        try:
            detail = fn()
            ok = detail is not False
            self.checks.append({"name": name, "ok": ok, "detail": None if detail in (None, True, False) else str(detail)[:600], "s": round(time.time() - t0, 2)})
            return ok
        except Exception as e:  # noqa: BLE001
            self.checks.append({"name": name, "ok": False, "detail": f"{type(e).__name__}: {str(e)[:600]}", "s": round(time.time() - t0, 2)})
            return False

    def anomalies(self) -> dict:
        def benign(t: str) -> bool:
            return any(p.search(t) for p in BENIGN)

        return {
            "console_errors": [c for c in self.console if c["type"] == "error" and not benign(c["text"])],
            "console_warnings": [c for c in self.console if c["type"] == "warning" and not benign(c["text"])],
            "page_errors": self.page_errors,
            "failed_requests": [r for r in self.failed_requests if "favicon" not in r],
            "bad_responses": [r for r in self.bad_responses if "favicon" not in r],
            "bad_responses_raw": self.bad_responses,
        }

    def dump(self, path: str | Path, **extra) -> dict:
        report = {
            **extra,
            "checks": self.checks,
            "all_ok": all(c["ok"] for c in self.checks),
            "anomalies": self.anomalies(),
            "console_all": self.console,
            "ws": self.ws,
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(report, indent=1))
        return report


def summarize(report: dict) -> str:
    lines = [f"all_ok={report['all_ok']}"]
    for c in report["checks"]:
        lines.append(f"  [{'PASS' if c['ok'] else 'FAIL'}] {c['name']}" + (f" -- {c['detail']}" if c["detail"] else ""))
    a = report["anomalies"]
    for k, v in a.items():
        if v:
            lines.append(f"  {k}: {len(v)}")
            for item in v[:6]:
                lines.append(f"     - {str(item)[:300]}")
    lines.append(f"  ws: " + ", ".join(f"{w['url'].split('?')[0]} sent={w['sent']} recv={w['recv']} closed={w['closed']}" for w in report["ws"]))
    return "\n".join(lines)


def expect(cond, detail) -> str:
    """Raise AssertionError(detail) unless cond; return 'ok: detail' otherwise."""
    if not cond:
        raise AssertionError(detail)
    return f"ok: {detail}"
