"""Drive the admindash app and its /admin dashboard in Chromium.

    cd /tmp && <driver venv>/bin/python <this> <frontend_url> <backend_url> <label>
"""

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

FRONTEND, BACKEND, LABEL = sys.argv[1], sys.argv[2], sys.argv[3]
SHOTS = Path(__file__).parent / "shots"
SHOTS.mkdir(exist_ok=True)
out = {"label": LABEL}
console, failed = [], []

with sync_playwright() as p:
    b = p.chromium.launch(
        executable_path="/opt/pw-browsers/chromium",
        args=["--no-sandbox", "--no-proxy-server"],
    )
    page = b.new_page()
    page.on("console", lambda m: console.append({"type": m.type, "text": m.text[:300]}))
    page.on("pageerror", lambda e: console.append({"type": "pageerror", "text": str(e)[:300]}))
    page.on(
        "response",
        lambda r: failed.append({"status": r.status, "url": r.url}) if r.status >= 400 else None,
    )

    # 1. the app's own page
    page.goto(FRONTEND, wait_until="networkidle", timeout=90000)
    page.wait_for_selector("#heading", timeout=60000)
    page.click("#add")
    page.wait_for_function("document.querySelector('#nwidgets').innerText !== '0'", timeout=30000)
    page.click("#add")
    page.wait_for_function("document.querySelector('#nwidgets').innerText === '2'", timeout=30000)
    out["app_nwidgets"] = page.inner_text("#nwidgets")
    out["app_rows"] = page.locator(".w").all_inner_texts()
    page.screenshot(path=str(SHOTS / f"{LABEL}_app.png"))

    # 2. the admin dashboard on the backend
    for name, url in (
        ("admin_index", BACKEND + "/admin/"),
        ("admin_list", BACKEND + "/admin/widget/list"),
        ("admin_create", BACKEND + "/admin/widget/create"),
        ("frontend_admin", FRONTEND.rstrip("/") + "/admin/"),
    ):
        try:
            r = page.goto(url, wait_until="domcontentloaded", timeout=60000)
            out[name + "_status"] = r.status if r else None
            out[name + "_body"] = page.inner_text("body")[:200]
            page.screenshot(path=str(SHOTS / f"{LABEL}_{name}.png"))
        except Exception as exc:  # noqa: BLE001
            out[name + "_status"] = f"{type(exc).__name__}: {exc}"[:200]

    b.close()

out["console"] = console
out["failed_requests"] = failed
print(json.dumps(out, indent=2))
