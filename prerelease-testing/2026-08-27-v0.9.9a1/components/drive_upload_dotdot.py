"""Probe the residual '..' sanitizer edge through the live buffered endpoint.

A raw multipart filename of literally '..' (or './../.', '..\\', '/..') is
sanitized to '..', so get_upload_dir() / file.path points to the upload dir's
PARENT. This confirms _sanitize_upload_filename can still return a traversal
token for pathological all-dots names (shared by streamed + buffered paths).
Usage: python drive_upload_dotdot.py <frontend> <backend>
"""

import json
import sys

import httpx
from playwright.sync_api import sync_playwright

FRONTEND = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:3380"
BACKEND = sys.argv[2].rstrip("/") if len(sys.argv) > 2 else "http://localhost:8380"
HANDLER = "reflex___state____state.comp_app___comp_app____upload_state.handle_upload"
CASES = ["..", "./../.", "..\\", "/..", "..."]

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = browser.new_context().new_page()
    page.goto(FRONTEND + "/upload", wait_until="networkidle", timeout=60000)
    page.wait_for_function("() => window.sessionStorage.getItem('token')", timeout=20000)
    page.wait_for_timeout(1500)
    token = page.evaluate("() => window.sessionStorage.getItem('token')")
    browser.close()

print("TOKEN:", token)
with httpx.Client(timeout=30, trust_env=False) as client:
    for raw in CASES:
        r = client.post(
            BACKEND + "/_upload",
            headers={"Reflex-Client-Token": token, "Reflex-Event-Handler": HANDLER},
            files={"files": (raw, b"x", "application/octet-stream")},
        )
        saved_tail = None
        err = None
        for line in r.text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            for _s, fields in obj.get("delta", {}).items():
                if "saved_rx_state_" in fields and fields["saved_rx_state_"]:
                    saved_tail = fields["saved_rx_state_"][-1]
            # server errors surface as an event / exception in the stream
            if "error" in str(obj).lower():
                err = str(obj)[:200]
        print(f"raw={raw!r:9} status={r.status_code} saved_tail={saved_tail!r} err={err}")
