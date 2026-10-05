"""Verifier control: documented rx.upload + submit-button scopes.

Usage: s_upbtn.py <base_url> <outdir>
"""

import sys
import time
from pathlib import Path

sys.argv = [sys.argv[0], "upbtn", *sys.argv[1:]]
from playwright.sync_api import sync_playwright  # noqa: E402
from wsdrive import BASE, OUT, attach, dump, errors, log, txt  # noqa: E402

UPLOAD_FILE = OUT / "upload_me.txt"
UPLOAD_FILE.write_text("verifier control upload\n")

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    page = ctx.new_page()
    attach(page, "c1")
    page.goto(f"{BASE}/upbtn", wait_until="networkidle")
    page.wait_for_selector("#ubgot", timeout=30000)
    time.sleep(1.0)

    # documented pattern: upload zone + SIBLING submit button
    page.set_input_files("#u3 input[type=file]", str(UPLOAD_FILE))
    page.wait_for_timeout(600)
    before = len(errors)
    page.click("#upsib")
    page.wait_for_timeout(2000)
    log("[A sibling button -> upload_files] got=", txt(page, "#ubgot"),
        " pageerrors=", errors[before:])

    page.click("#upclear")
    page.wait_for_timeout(400)

    # button nested INSIDE the rx.upload children
    page.set_input_files("#u4 input[type=file]", str(UPLOAD_FILE))
    page.wait_for_timeout(600)
    before = len(errors)
    page.click("#upinner")
    page.wait_for_timeout(2000)
    log("[B button inside rx.upload -> upload_files] got=", txt(page, "#ubgot"),
        " pageerrors=", errors[before:])

    page.screenshot(path=str(OUT / "upbtn_final.png"))
    dump("upbtn")
    from wsdrive import console_log, net  # noqa: E402

    log("== console ==")
    for line in console_log:
        if any(s in line for s in ("Hey developer", "connecting", "connected", "React DevTools")):
            continue
        log("  ", line)
    log("== pageerrors ==", errors)
    log("== net ==", net)
    ctx.close()
    b.close()
