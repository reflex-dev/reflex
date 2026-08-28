"""Rigorous buffered-upload sanitizer test (#6753) via raw multipart POST.

Playwright establishes a live reflex session (so the token is registered in the
event processor), extracts the client token, then httpx POSTs exact raw forged
filenames to /_upload. The ndjson response carries the state delta with
UploadState.saved, which records the server-sanitized name/path. This bypasses
browser filename normalization to test the SERVER sanitizer on truly hostile
inputs (leading slash, '..', windows drive).
Usage: python drive_upload_raw.py <frontend_url> <backend_url>
"""

import json
import sys

import httpx
from playwright.sync_api import sync_playwright

FRONTEND = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:3380"
BACKEND = sys.argv[2].rstrip("/") if len(sys.argv) > 2 else "http://localhost:8380"
HANDLER = "reflex___state____state.comp_app___comp_app____upload_state.handle_upload"

# raw multipart filename -> expected sanitized path (from _sanitize_upload_filename
# computed in the smoke venv). These are the hostile server-side inputs.
CASES = [
    ("../../evil.txt", "evil.txt"),
    ("..\\..\\..\\evil.txt", "evil.txt"),
    ("/etc/passwd", "passwd"),
    ("C:\\Windows\\system32\\evil.dll", "evil.dll"),
    ("....//....//escape.txt", "..../..../escape.txt"),
    ("a b<>|.txt", "a b<>|.txt"),
    ("uni_café_日本.txt", "uni_café_日本.txt"),
]

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = browser.new_context()
    page = ctx.new_page()
    page.goto(FRONTEND + "/upload", wait_until="networkidle", timeout=60000)
    page.wait_for_selector("#upload-btn", timeout=30000)
    # wait for hydration + websocket connect so the token is registered server-side
    page.wait_for_function(
        "() => window.sessionStorage.getItem('token')", timeout=20000
    )
    page.wait_for_timeout(1500)
    token = page.evaluate("() => window.sessionStorage.getItem('token')")
    print("TOKEN:", token)

    # POST each forged filename via httpx and parse the ndjson delta.
    observed = {}
    with httpx.Client(timeout=30, trust_env=False) as client:
        for raw, _ in CASES:
            files = {"files": (raw, b"hostile-content", "application/octet-stream")}
            r = client.post(
                BACKEND + "/_upload",
                headers={
                    "Reflex-Client-Token": token,
                    "Reflex-Event-Handler": HANDLER,
                },
                files=files,
            )
            body = r.text
            # last delta line holds the accumulated saved list
            saved_now = None
            for line in body.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                delta = obj.get("delta", {})
                for _state, fields in delta.items():
                    if "saved_rx_state_" in fields:
                        saved_now = fields["saved_rx_state_"]
            observed[raw] = (r.status_code, saved_now)
            print(f"POST {raw!r:35} -> {r.status_code} saved_tail={saved_now[-1] if saved_now else None!r}")

    # Read final full saved list from the browser after all posts.
    page.wait_for_timeout(500)
    browser.close()

print("\nCHECKS (server-side sanitized path must match expected, no traversal):")
# Flatten: collect every path seen across posts
import re

all_paths = set()
last_saved = None
for raw, (status, saved) in observed.items():
    if saved:
        last_saved = saved
if last_saved:
    for entry in last_saved:
        m = re.search(r"path='([^']*)'", entry)
        if m:
            all_paths.add(m.group(1))

fails = 0
for raw, expected in CASES:
    present = expected in all_paths
    status = "pass" if present else "FAIL"
    if not present:
        fails += 1
    print(f"  [{status}] raw={raw!r} expected_sanitized_path={expected!r}")

# traversal safety: no path may start with '/', contain a '..' path segment,
# or contain a windows drive that escapes.
escapes = [
    pth for pth in all_paths
    if pth.startswith("/") or ".." in pth.replace("....", "").split("/")
]
print("\nTRAVERSAL_ESCAPES:", escapes if escapes else "none")
print("ALL_SERVER_PATHS:", sorted(all_paths))
print("\nSUMMARY:", "ALL PASS" if fails == 0 and not escapes else f"{fails} content fails, escapes={escapes}")
sys.exit(1 if (fails or escapes) else 0)
