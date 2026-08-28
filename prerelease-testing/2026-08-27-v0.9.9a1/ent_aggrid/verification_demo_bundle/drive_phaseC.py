"""Phase C driver: verify /formatters renders with the fixed bundling on 0.9.8.

Opens /formatters, waits for the ag-grid to render, checks the memo-based
"row counter" renderer produced clickable buttons, clicks one, switches to the
"State" tab (column defs served from FormatterState — the path that triggers
rxe's serialize_lambda on the backend), screenshots, and dumps console errors.
"""

import json
import sys

from playwright.sync_api import sync_playwright

base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3808"
out = sys.argv[2] if len(sys.argv) > 2 else "shotsC"

console_msgs = []
failed_requests = []

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = browser.new_page()
    page.on(
        "console",
        lambda m: console_msgs.append({"type": m.type, "text": m.text[:300]}),
    )
    page.on(
        "requestfailed",
        lambda r: failed_requests.append({"url": r.url, "err": r.failure}),
    )
    page.on(
        "response",
        lambda r: r.status >= 400
        and failed_requests.append({"url": r.url, "status": r.status}),
    )

    resp = page.goto(f"{base}/formatters", wait_until="networkidle", timeout=60000)
    print("GET /formatters ->", resp.status)
    page.wait_for_selector(".ag-root", timeout=30000)
    page.wait_for_timeout(2000)
    # Inline tab grid: memo renderer buttons in the "# Clicks" column.
    buttons = page.locator(
        "#formatter-grid-bare .ag-cell button, div[id*='formatter-grid-bare'] button"
    )
    # Fallback: any button inside an ag-cell.
    cell_buttons = page.locator(".ag-cell button")
    print("ag-cell buttons:", cell_buttons.count())
    if cell_buttons.count():
        cell_buttons.first.click()
        page.wait_for_timeout(1000)
        print("after click, first button text:", cell_buttons.first.inner_text()[:60])
    # Check formatter outputs: flag emoji and currency.
    body_text = page.inner_text("body")
    print("has US flag:", "\U0001f1fa\U0001f1f8" in body_text)
    print("has currency $12,345.68:", "$12,345.68" in body_text)
    page.screenshot(path=f"{out}_inline.png", full_page=True)
    # Switch to State tab -> triggers backend serialization of cols_defs lambdas.
    page.get_by_role("tab", name="State").click()
    page.wait_for_timeout(3000)
    page.screenshot(path=f"{out}_state.png", full_page=True)
    state_grid_cells = page.locator("#formatter-grid-state .ag-cell").count()
    print("state tab ag-cells:", state_grid_cells)
    browser.close()

errors = [
    m
    for m in console_msgs
    if m["type"] == "error"
    and "License Key Not Found" not in m["text"]
    and "license" not in m["text"].lower()
    and "AG Grid" not in m["text"]
]
print("console errors (non-license):", json.dumps(errors[:10], indent=1))
print("failed requests:", json.dumps(failed_requests[:10], indent=1))
