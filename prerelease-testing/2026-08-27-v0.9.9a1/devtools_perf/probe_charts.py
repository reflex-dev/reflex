"""Quick probe of the /charts page: console + DOM state."""

import os

from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("BASE_URL", "http://localhost:3500")

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = browser.new_context().new_page()
    msgs = []
    page.on("console", lambda m: msgs.append(f"[{m.type}] {m.text[:400]}"))
    page.on("pageerror", lambda e: msgs.append(f"[pageerror] {e}"))
    page.goto(BASE_URL + "/charts", wait_until="load", timeout=60000)
    page.wait_for_timeout(8000)
    print("URL:", page.url)
    print("page-root exists:", page.locator("#page-root").count())
    print("the-plot exists:", page.locator("#the-plot").count())
    print("body snippet:", page.inner_text("body")[:400].replace("\n", " | "))
    page.screenshot(path="charts_probe.png")
    for m in msgs:
        print(m)
    browser.close()
