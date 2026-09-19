"""Probe HTTP status + rendered content for every route of the bpapp test app.

Usage: python routes_probe.py <base_url> <out_json> [label]
Requires the driver venv (playwright) + httpx.
"""

import json
import sys
import urllib.request

from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
OUT = sys.argv[2]
LABEL = sys.argv[3] if len(sys.argv) > 3 else "run"

PATHS = [
    "/",
    "/apple",
    "/apple/",
    "/app",
    "/app/",
    "/appx",
    "/app/apple",
    "/app/app",
    "/app/about",
    "/app/components",
    "/app/assets",
    "/app/items/7?x=1",
    "/app/sitemap.xml",
    "/app/components/logo.svg",
    "/app/apple/note.txt",
]

result = {"label": LABEL, "base": BASE, "routes": []}

# 1) raw HTTP status codes (no JS)
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
for p in PATHS:
    entry = {"path": p}
    try:
        with opener.open(BASE + p, timeout=20) as r:
            body = r.read().decode("utf-8", "replace")
            entry["http_status"] = r.status
            entry["len"] = len(body)
            mark = [
                line
                for line in body.split("PAGEMARK:")[1:2]
            ]
            entry["pagemark"] = mark[0][:20].split("<")[0] if mark else None
            entry["content_encoding"] = r.headers.get("content-encoding")
            entry["content_type"] = r.headers.get("content-type")
    except Exception as e:  # noqa: BLE001
        entry["http_status"] = getattr(e, "code", None)
        entry["error"] = f"{type(e).__name__}: {e}"
        try:
            entry["len"] = len(e.read())  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass
    result["routes"].append(entry)

# 2) browser render
with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for entry in result["routes"]:
        p = entry["path"]
        if p.endswith((".svg", ".txt", ".xml")):
            continue
        ctx = browser.new_context()
        page = ctx.new_page()
        console_msgs = []
        failed = []
        bad_responses = []
        page.on(
            "console",
            lambda m: console_msgs.append({"type": m.type, "text": m.text[:400]}),
        )
        page.on("pageerror", lambda e: console_msgs.append({"type": "pageerror", "text": str(e)[:400]}))
        page.on("requestfailed", lambda r: failed.append(r.url))
        page.on(
            "response",
            lambda r: bad_responses.append({"url": r.url, "status": r.status})
            if r.status >= 400
            else None,
        )
        try:
            resp = page.goto(BASE + p, wait_until="networkidle", timeout=45000)
            entry["nav_status"] = resp.status if resp else None
            page.wait_for_timeout(1200)
            entry["rendered_title"] = page.title()
            try:
                entry["rendered_pagemark"] = page.locator("#pagemark").first.inner_text(timeout=2500)
            except Exception:  # noqa: BLE001
                entry["rendered_pagemark"] = None
            entry["body_head"] = page.locator("body").inner_text()[:220].replace("\n", " | ")
            entry["final_url"] = page.url
        except Exception as e:  # noqa: BLE001
            entry["nav_error"] = f"{type(e).__name__}: {e}"[:300]
        entry["console"] = [
            m for m in console_msgs if m["type"] in ("error", "warning", "pageerror")
        ]
        entry["console_all_count"] = len(console_msgs)
        entry["failed_requests"] = failed
        entry["bad_responses"] = bad_responses
        ctx.close()
    browser.close()

with open(OUT, "w") as f:
    json.dump(result, f, indent=2)
print(json.dumps(result, indent=2)[:200])
