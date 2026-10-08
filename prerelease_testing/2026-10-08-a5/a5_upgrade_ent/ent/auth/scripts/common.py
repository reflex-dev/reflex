"""Shared helpers for the ent_auth_mcp_redis Playwright drivers."""

import json
import re
import subprocess
import time
from pathlib import Path

import playwright

assert any(v in playwright.__file__ for v in ("/scratchpad/envs/driver/", "/scratchpad/envs/ent_auth2-drv/")), playwright.__file__

W = Path("/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/apps/a5_upgrade_ent/ent/auth")
CHROMIUM = "/opt/pw-browsers/chromium"


def attach(page, sink: dict) -> None:
    """Record console, page errors, failed requests, >=400 responses, ws frames."""
    sink.setdefault("console", [])
    sink.setdefault("page_errors", [])
    sink.setdefault("failed_requests", [])
    sink.setdefault("http_errors", [])
    sink.setdefault("ws_frames", {"sent": 0, "received": 0})
    page.on("console", lambda m: sink["console"].append({"type": m.type, "text": m.text[:500], "url": page.url.split("?")[0]}))
    page.on("pageerror", lambda e: sink["page_errors"].append(str(e)[:1000]))
    page.on("requestfailed", lambda r: sink["failed_requests"].append({"url": r.url.split("?")[0], "failure": r.failure, "method": r.method}))
    page.on("response", lambda r: sink["http_errors"].append({"url": r.url.split("?")[0], "status": r.status}) if r.status >= 400 else None)

    def on_ws(ws):
        ws.on("framesent", lambda p: sink["ws_frames"].__setitem__("sent", sink["ws_frames"]["sent"] + 1))
        ws.on("framereceived", lambda p: sink["ws_frames"].__setitem__("received", sink["ws_frames"]["received"] + 1))
    page.on("websocket", on_ws)


def login(page, user: str = "alice", button: str = "Login with Generic") -> None:
    """From the /login palette, sign in via the mock IdP form."""
    page.get_by_role("button", name=button).click()
    page.wait_for_url(re.compile("/oauth2/authorize"))
    page.locator(f'button[name="sub"][value="{user}"]').click()


def end_session(page) -> None:
    page.wait_for_url(re.compile("/oauth2/end_session"))
    page.get_by_role("button", name="End session", exact=True).click()


def redis_dump(pattern: str = "*", port: int = 8629) -> dict:
    """Return {key: raw bytes as latin-1 str} for keys matching pattern (small DB)."""
    keys = subprocess.run(["redis-cli", "-p", str(port), "--scan", "--pattern", pattern], capture_output=True, text=True).stdout.split()
    out = {}
    for k in keys:
        t = subprocess.run(["redis-cli", "-p", str(port), "type", k], capture_output=True, text=True).stdout.strip()
        if t == "string":
            v = subprocess.run(["redis-cli", "-p", str(port), "--no-raw", "get", k], capture_output=True, text=True).stdout
            out[k] = v
        else:
            out[k] = f"<{t}>"
    return out


def storage_snapshot(page) -> dict:
    return page.evaluate("""() => ({
        local: Object.fromEntries(Object.entries(localStorage)),
        session: Object.fromEntries(Object.entries(sessionStorage)),
        cookie: document.cookie,
    })""")


def save(name: str, data) -> None:
    (W / "logs" / name).write_text(json.dumps(data, indent=2, default=str))
