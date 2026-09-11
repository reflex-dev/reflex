"""Drive the wraptapp in Chromium and record the digest after each mutation.

    cd /tmp && <driver venv>/bin/python <this> <frontend_url> <label>
"""

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

URL, LABEL = sys.argv[1], sys.argv[2]
SHOTS = Path(__file__).parent / "shots"
SHOTS.mkdir(exist_ok=True)
out = {"label": LABEL, "steps": []}
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
    page.goto(URL, wait_until="networkidle", timeout=90000)
    page.wait_for_selector("#digest", timeout=60000)
    out["initial_digest"] = page.inner_text("#digest")

    def step(btn, expect):
        before = page.inner_text("#digest")
        page.click(btn)
        page.wait_for_function(
            f"document.querySelector('#digest').innerText === {expect!r}", timeout=30000
        )
        out["steps"].append({
            "button": btn,
            "before": before,
            "after": page.inner_text("#digest"),
            "items": page.inner_text("#items"),
            "counts": page.inner_text("#counts"),
            "tags": page.inner_text("#tags"),
            "rendered_items": page.locator(".item").count(),
        })

    # items=1 counts={x:1} nested[0]=0 score=0 tags=1 bg=0  ->  "1|1|0|0|1|0"
    step("#b_list", "2|1|0|0|1|0")
    step("#b_dict", "2|3|0|0|1|0")
    step("#b_nested", "2|3|1|0|1|0")
    step("#b_dc", "2|3|1|1|2|0")
    step("#b_pop", "1|1|1|1|2|0")
    step("#b_bg", "1|1|1|1|5|3")
    page.screenshot(path=str(SHOTS / f"wrapt_{LABEL}.png"))
    b.close()

out["console_errors"] = [c for c in console if c["type"] in ("error", "pageerror")]
out["failed_requests"] = failed
print(json.dumps(out, indent=2))
