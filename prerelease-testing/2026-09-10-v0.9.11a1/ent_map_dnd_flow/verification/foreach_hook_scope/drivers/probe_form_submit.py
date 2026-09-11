"""Click the first submit button on /form and report errors + the state log."""

import json
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
OUT = sys.argv[2]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context(viewport={"width": 900, "height": 700})
    page = ctx.new_page()
    errs, perrs = [], []
    page.on(
        "console",
        lambda m: errs.append(f"{m.type}: {m.text[:400]}") if m.type == "error" else None,
    )
    page.on("pageerror", lambda e: perrs.append(str(e)[:400]))
    page.goto(BASE + "/form", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(2000)
    before = page.locator("body").inner_text()
    page.locator("button[type=submit]").nth(1).click()
    page.wait_for_timeout(2500)
    print(
        json.dumps(
            {
                "before": before.replace("\n", " | ")[:200],
                "after": page.locator("body").inner_text().replace("\n", " | ")[:300],
                "console_errors": errs[:6],
                "page_errors": perrs[:6],
            },
            indent=2,
        )
    )
    page.screenshot(path=f"{OUT}_form_submit.png")
    ctx.close()
    b.close()
