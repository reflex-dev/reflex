"""Verify the minimal ag-grid app renders, incl. the lambda cell_renderer column."""

import sys

from playwright.sync_api import sync_playwright

url = sys.argv[1]
shot = sys.argv[2]

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = browser.new_page()
    console_errors = []
    page.on(
        "console",
        lambda m: console_errors.append(m.text) if m.type == "error" else None,
    )
    page.goto(url, wait_until="networkidle", timeout=60000)
    page.wait_for_selector("#title", timeout=30000)
    page.wait_for_selector(".ag-cell", timeout=30000)
    cells = page.locator(".ag-cell").all_inner_texts()
    print("cells sample:", cells[:12])
    headers = page.locator(".ag-header-cell-text").all_inner_texts()
    print("headers:", headers)
    tomato = page.locator(".ag-cell p, .ag-cell span.rt-Text, .ag-cell .rt-Text")
    print("styled renderer nodes:", tomato.count())
    for i in range(min(tomato.count(), 3)):
        el = tomato.nth(i)
        print(
            "  node text=", el.inner_text(),
            "color=", el.evaluate("e => getComputedStyle(e).color"),
        )
    page.screenshot(path=shot, full_page=True)
    print("console errors:", [e[:100] for e in console_errors[:10]])
    browser.close()
