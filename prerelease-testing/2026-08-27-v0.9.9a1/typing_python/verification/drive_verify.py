"""Playwright driver: verify alias-var assignment behavior end-to-end."""

import sys
import time

from playwright.sync_api import sync_playwright

url = sys.argv[1]
shotdir = sys.argv[2]

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = browser.new_page()
    console_msgs = []
    page.on("console", lambda m: console_msgs.append(f"[{m.type}] {m.text}"))
    page.goto(url, wait_until="networkidle", timeout=120000)

    # wait for hydration: initial values present
    page.wait_for_selector("#alias-val", timeout=60000)
    for _ in range(60):
        if (
            page.inner_text("#alias-val") == "a"
            and page.inner_text("#plain-val") == "init"
        ):
            break
        time.sleep(0.5)
    print("initial alias-val:", page.inner_text("#alias-val"))
    print("initial plain-val:", page.inner_text("#plain-val"))
    page.screenshot(path=f"{shotdir}/01_initial.png")

    # control: plain var assignment should work
    page.click("#btn-plain")
    ok_plain = False
    for _ in range(20):
        if page.inner_text("#plain-val") == "changed":
            ok_plain = True
            break
        time.sleep(0.5)
    print("plain assignment worked:", ok_plain)

    # alias var assignment: claimed to crash server-side, UI never updates
    page.click("#btn-alias")
    ok_alias = False
    for _ in range(12):
        if page.inner_text("#alias-val") == "b":
            ok_alias = True
            break
        time.sleep(0.5)
    print("alias assignment worked:", ok_alias)
    page.screenshot(path=f"{shotdir}/02_after_clicks.png")

    print("--- console messages ---")
    for m in console_msgs:
        print(m)
    browser.close()
