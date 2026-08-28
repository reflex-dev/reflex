"""Probe just the /form/<id> entry page: renders? console errors? submit works?

Usage: python probe_entry.py <label> <url> <form_id> [field_name]
"""

import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

LABEL, URL, FORM_ID = sys.argv[1:4]
FIELD = sys.argv[4] if len(sys.argv) > 4 else "favorite_food"
ART = Path(__file__).parent / "artifacts"
ART.mkdir(exist_ok=True)
console_msgs = []

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = browser.new_context(viewport={"width": 1280, "height": 1000}).new_page()
    page.on("console", lambda m: console_msgs.append({"type": m.type, "text": m.text}))
    page.goto(URL.rstrip("/") + f"/form/{FORM_ID}", wait_until="load")
    time.sleep(3.0)
    body = page.inner_text("body")
    crashed = "An error occurred while rendering this page" in body
    fm = [m for m in console_msgs if "FormMessage" in m["text"]]
    page.screenshot(path=str(ART / f"{LABEL}_probe_entry.png"))
    submitted = False
    if not crashed:
        try:
            page.fill(f'input[name="{FIELD}"]', f"pizza-{LABEL}")
            page.get_by_role("button", name="Submit").click()
            page.wait_for_url(re.compile(r".*/success.*"), timeout=15000)
            submitted = True
        except Exception as e:
            print("submit failed:", e)
    print(json.dumps({
        "label": LABEL,
        "crashed": crashed,
        "formmessage_console_errors": len(fm),
        "submitted": submitted,
    }))
    (ART / f"{LABEL}_probe_console.json").write_text(json.dumps(console_msgs, indent=2))
    browser.close()
