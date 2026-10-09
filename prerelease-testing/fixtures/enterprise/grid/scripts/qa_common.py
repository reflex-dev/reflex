"""Shared Playwright capture helpers for the ent_grid cluster drivers (adapted from the 10-06 ent_demos cluster).

Every driver opens a `Session`, which records console messages (all levels),
page errors, failed requests, HTTP >= 400 responses and websocket frame
counts/samples for every page in the browser context, plus named checks.
`Session.save()` writes a JSON report next to the screenshots.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

CHROMIUM = "/opt/pw-browsers/chromium"

BENIGN_CONSOLE = [
    re.compile(r"Hey developer.*HydrateFallback|reactrouter\.com/start/framework/route-module"),
    re.compile(r"\[vite\] (connecting|connected)"),
    re.compile(r"Download the React DevTools"),
    # Expected AG Grid / AG Charts unlicensed trial banners (enterprise demos).
    re.compile(r"\*{5,}"),
    re.compile(r"AG Grid Enterprise License|AG Charts Enterprise License", re.I),
    re.compile(r"License Key Not Found|All AG Grid (and AG Charts )?Enterprise features are unlocked for trial", re.I),
    re.compile(r"If you want to hide the watermark|ag-grid\.com/(javascript-data-grid/)?licensing|info@ag-grid\.com", re.I),
    re.compile(r"AG Charts.*licen|ag-charts.*licen", re.I),
]


def is_benign(text: str) -> bool:
    """Return True for known-benign console chatter."""
    return any(p.search(text) for p in BENIGN_CONSOLE)


class Session:
    """A browser session with full capture of console/network/websocket activity."""

    def __init__(self, name: str, out_dir: Path, headless: bool = True):
        self.name = name
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.headless = headless
        self.console: list[dict[str, Any]] = []
        self.page_errors: list[dict[str, Any]] = []
        self.failed_requests: list[dict[str, Any]] = []
        self.http_errors: list[dict[str, Any]] = []
        self.ws: dict[str, dict[str, Any]] = {}
        self.requests: list[dict[str, Any]] = []
        self.checks: list[dict[str, Any]] = []
        self.notes: list[str] = []
        self.t0 = time.time()
        self._pw = None
        self.browser: Browser | None = None
        self.contexts: list[BrowserContext] = []

    def __enter__(self) -> "Session":
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(executable_path=CHROMIUM, headless=self.headless)
        return self

    def __exit__(self, *exc) -> None:
        if exc[0] is not None:
            self.check("driver_exception", False, f"{exc[0].__name__}: {exc[1]}")
        try:
            for ctx in self.contexts:
                ctx.close()
            if self.browser:
                self.browser.close()
        finally:
            if self._pw:
                self._pw.stop()
        self.save()

    def _ts(self) -> float:
        return round(time.time() - self.t0, 2)

    def new_context(self, label: str = "ctx", **kwargs) -> BrowserContext:
        """Create a browser context whose pages are all captured."""
        assert self.browser is not None
        ctx = self.browser.new_context(viewport={"width": 1400, "height": 900}, **kwargs)
        self.contexts.append(ctx)
        ctx.on("page", lambda p: self._hook(p, label))
        return ctx

    def new_page(self, ctx: BrowserContext | None = None, label: str = "ctx") -> Page:
        """Create a captured page (in a fresh context unless one is given)."""
        if ctx is None:
            ctx = self.new_context(label)
        return ctx.new_page()

    def _hook(self, page: Page, label: str) -> None:
        page.on(
            "console",
            lambda m: self.console.append({
                "t": self._ts(),
                "ctx": label,
                "type": m.type,
                "text": m.text[:2000],
                "url": page.url,
                "location": m.location,
                "benign": is_benign(m.text),
            }),
        )
        page.on("pageerror", lambda e: self.page_errors.append({"t": self._ts(), "ctx": label, "error": str(e)[:3000], "url": page.url}))
        page.on(
            "requestfailed",
            lambda r: self.failed_requests.append({"t": self._ts(), "ctx": label, "url": r.url, "method": r.method, "failure": r.failure}),
        )

        def on_response(resp):
            if resp.status >= 400:
                self.http_errors.append({"t": self._ts(), "ctx": label, "url": resp.url, "status": resp.status})

        page.on("response", on_response)
        page.on(
            "request",
            lambda r: self.requests.append({"t": self._ts(), "ctx": label, "url": r.url, "method": r.method})
            if ("localhost" in r.url and "/@" not in r.url and "node_modules" not in r.url and not r.url.endswith((".js", ".css", ".jsx", ".mjs", ".map", ".woff2", ".ico", ".svg", ".png")))
            else None,
        )

        def on_ws(ws):
            rec = self.ws.setdefault(ws.url, {"ctx": label, "sent": 0, "recv": 0, "sent_samples": [], "recv_samples": [], "closed": False})

            def sent(payload):
                rec["sent"] += 1
                if len(rec["sent_samples"]) < 60:
                    rec["sent_samples"].append(str(payload)[:600])

            def recv(payload):
                rec["recv"] += 1
                if len(rec["recv_samples"]) < 60:
                    rec["recv_samples"].append(str(payload)[:600])

            ws.on("framesent", sent)
            ws.on("framereceived", recv)
            ws.on("close", lambda _: rec.__setitem__("closed", True))

        page.on("websocket", on_ws)

    def check(self, name: str, ok: bool, detail: Any = "") -> bool:
        """Record a named pass/fail check and echo it."""
        self.checks.append({"t": self._ts(), "name": name, "ok": bool(ok), "detail": detail if isinstance(detail, (str, int, float, list, dict, bool)) or detail is None else str(detail)})
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {str(detail)[:300]}", flush=True)
        return bool(ok)

    def note(self, text: str) -> None:
        """Record a free-form observation."""
        self.notes.append(text)
        print(f"[NOTE] {text}", flush=True)

    def shot(self, page: Page, name: str, full_page: bool = False) -> None:
        """Save a screenshot under the output dir."""
        path = self.out_dir / f"{self.name}-{name}.jpg"
        try:
            page.screenshot(path=str(path), full_page=full_page, type="jpeg", quality=45)
        except Exception as e:  # noqa: BLE001
            self.note(f"screenshot {name} failed: {e}")

    def anomalies(self) -> dict[str, Any]:
        """Summarise non-benign console/page/network anomalies."""
        return {
            "console_errors": [c for c in self.console if c["type"] == "error" and not c["benign"]],
            "console_warnings": [c for c in self.console if c["type"] == "warning" and not c["benign"]],
            "page_errors": self.page_errors,
            "failed_requests": self.failed_requests,
            "http_errors": self.http_errors,
        }

    def save(self) -> Path:
        """Write the JSON report and print a summary."""
        an = self.anomalies()
        report = {
            "name": self.name,
            "python": sys.executable,
            "checks": self.checks,
            "notes": self.notes,
            "summary": {
                "checks_failed": [c["name"] for c in self.checks if not c["ok"]],
                "n_checks": len(self.checks),
                "console_total": len(self.console),
                "console_benign": sum(1 for c in self.console if c["benign"]),
                **{k: len(v) for k, v in an.items()},
            },
            "anomalies": an,
            "console_all": self.console,
            "websockets": self.ws,
            "requests": self.requests[-400:],
        }
        path = self.out_dir / f"{self.name}.json"
        path.write_text(json.dumps(report, indent=1, default=str))
        print(json.dumps(report["summary"], indent=1), flush=True)
        for kind in ("console_errors", "console_warnings", "page_errors", "failed_requests", "http_errors"):
            for item in an[kind][:12]:
                print(f"  {kind}: {json.dumps(item, default=str)[:400]}", flush=True)
        return path


SB = __import__("os").environ["SB"]


def assert_driver_and_server(expected_venv: str) -> dict[str, str]:
    """Guard: this driver runs in the driver venv and the live server runs from `expected_venv`.

    Checks the python running this script, the `reflex run` process recorded by
    start_server.sh, and where reflex / reflex_enterprise import from in that venv.
    """
    import subprocess

    assert ("/envs/" + __import__("os").environ.get("DRV_VENV", "driver") + "/") in sys.executable, sys.executable
    pid = (Path(__file__).resolve().parent.parent / "pids" / "current.pgid").read_text().strip()  # pgid == pid of the setsid reflex process (bin/start.sh)
    cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode()
    assert f"/envs/{expected_venv}/bin/" in cmdline, cmdline
    out = subprocess.run(
        [f"{SB}/envs/{expected_venv}/bin/python", "-I", "-c",
         "import reflex, importlib.metadata as m, importlib.util as u; "
         "print(reflex.__file__); "
         "spec = u.find_spec('reflex_enterprise'); "
         "print(spec.origin if spec else '(no reflex_enterprise: /envs/' + __import__('sys').prefix.split('/envs/')[1] + '/)'); "
         "print(m.version('reflex'), m.version('reflex-enterprise') if spec else '-')"],
        capture_output=True, text=True, check=True, cwd=SB,
    ).stdout.split("\n")
    assert f"/envs/{expected_venv}/" in out[0], out
    assert f"/envs/{expected_venv}/" in out[1], out
    info = {"server_cmdline": cmdline, "reflex": out[0], "reflex_enterprise": out[1], "versions": out[2]}
    print(f"[GUARD] driver={sys.executable} server venv={expected_venv} versions={out[2]}", flush=True)
    return info


def wait_hydrated(page: Page, timeout: float = 30000) -> None:
    """Wait for the Reflex websocket connection to be established (state hydrated)."""
    page.wait_for_load_state("domcontentloaded", timeout=timeout)
    page.wait_for_function(
        "() => !document.querySelector('[data-testid=\"connection-banner\"], .connection-banner') && document.readyState === 'complete'",
        timeout=timeout,
    )
    page.wait_for_timeout(800)
