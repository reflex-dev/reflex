"""Independent verifier driver for the form-designer FormMessage crash claim.

Usage: python drive_verify.py <label> <url>
Registers a fresh user (name derived from label), creates a form, adds one
text field, then opens /form/<id> and records whether the page hits the
error boundary and whether the FormMessage console error appears. If the
page renders, attempts to submit an entry.
Artifacts: ./artifacts/<label>_*.png, ./artifacts/<label>_results.json
"""

import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

LABEL, URL = sys.argv[1:3]
USERNAME = f"vuser_{LABEL}"
FORMNAME = f"VForm_{LABEL}"
PASSWORD = "S3cretPass!42"
ART = Path(__file__).parent / "artifacts"
ART.mkdir(exist_ok=True)

console_msgs = []
results = []


def check(name, ok, detail=""):
    results.append({"name": name, "ok": bool(ok), "detail": str(detail)[:600]})
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}")


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = browser.new_context(viewport={"width": 1280, "height": 1000})
    page = ctx.new_page()
    page.on("console", lambda m: console_msgs.append({"type": m.type, "text": m.text}))
    base = URL.rstrip("/")

    # register
    page.goto(base + "/register/", wait_until="load")
    page.locator('input[name="username"]').wait_for(timeout=30000)
    page.fill('input[name="username"]', USERNAME)
    page.fill('input[name="password"]', PASSWORD)
    page.fill('input[name="confirm_password"]', PASSWORD)
    page.get_by_role("button", name="Sign up").click()
    try:
        page.wait_for_url(re.compile(r".*/login.*"), timeout=20000)
        check("register", True)
    except Exception as e:
        check("register", False, e)

    # login (no auto-redirect expected; verify via protected page)
    page.fill('input[name="username"]', USERNAME)
    page.fill('input[name="password"]', PASSWORD)
    page.get_by_role("button", name="Sign in").click()
    time.sleep(3.0)
    page.goto(base + "/edit/form/", wait_until="load")
    try:
        page.locator('input[placeholder="Form Name"]').wait_for(timeout=20000)
        check("login authenticates", True)
    except Exception as e:
        check("login authenticates", False, e)

    # create form
    page.fill('input[placeholder="Form Name"]', FORMNAME)
    form_id = None
    try:
        page.wait_for_url(re.compile(r".*/edit/form/\d+.*"), timeout=20000)
        form_id = re.search(r"/edit/form/(\d+)", page.url).group(1)
        check("create form", True, f"id={form_id}")
    except Exception as e:
        check("create form", False, e)

    # add one text field
    try:
        page.get_by_role("button", name="Add Field").click()
        dlg = page.get_by_role("dialog").filter(has_text="Edit Field")
        dlg.locator('input[name="field_name"]').wait_for(timeout=15000)
        dlg.locator('input[name="field_name"]').fill("favorite_food")
        dlg.locator('input[name="field_prompt"]').fill("What is your favorite food?")
        dlg.get_by_role("button", name="Save").click()
        page.wait_for_url(re.compile(r".*/edit/form/\d+/?$"), timeout=15000)
        page.get_by_text("What is your favorite food?").first.wait_for(timeout=10000)
        check("add text field", True)
    except Exception as e:
        check("add text field", False, e)

    # entry/preview page
    if form_id:
        console_msgs.clear()
        page.goto(base + f"/form/{form_id}", wait_until="load")
        time.sleep(3.0)
        body = page.inner_text("body")
        crashed = "An error occurred while rendering this page" in body
        page.screenshot(path=str(ART / f"{LABEL}_entry_page.png"))
        fm_errors = [
            m for m in console_msgs
            if "FormMessage" in m["text"] and "FormField" in m["text"]
        ]
        check(
            "entry page renders WITHOUT error boundary",
            not crashed,
            f"FormMessage console errors: {len(fm_errors)}",
        )
        if fm_errors:
            print("  first FormMessage error:", fm_errors[0]["text"][:300])
        # attempt submit if rendered
        if not crashed:
            try:
                page.fill('input[name="favorite_food"]', f"pizza-{LABEL}")
                page.get_by_role("button", name="Submit").click()
                page.wait_for_url(re.compile(r".*/success.*"), timeout=15000)
                check("entry submits successfully", True, page.url)
                page.screenshot(path=str(ART / f"{LABEL}_entry_success.png"))
            except Exception as e:
                check("entry submits successfully", False, e)
                page.screenshot(path=str(ART / f"{LABEL}_entry_submit_fail.png"))
        else:
            check("entry submits successfully", False, "page crashed, cannot submit")

    (ART / f"{LABEL}_results.json").write_text(json.dumps(results, indent=2))
    (ART / f"{LABEL}_console.json").write_text(json.dumps(console_msgs, indent=2))
    browser.close()

print(json.dumps({"label": LABEL, "ok": all(r["ok"] for r in results)}))
