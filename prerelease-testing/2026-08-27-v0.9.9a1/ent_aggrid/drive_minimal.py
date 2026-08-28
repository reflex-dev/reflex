"""Drive the minimal rxe.ag_grid app: verify grid renders, sort works.

Usage: python drive_minimal.py <base_url> <shot_path> [expect_lambda_col]
"""

import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
SHOT = sys.argv[2]
EXPECT_LAMBDA = len(sys.argv) > 3 and sys.argv[3] == "1"

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = browser.new_page(viewport={"width": 1200, "height": 800})
    console = []
    errors = []
    page.on("console", lambda m: console.append((m.type, m.text[:300])))
    page.on("pageerror", lambda e: errors.append(str(e)[:500]))
    page.goto(BASE + "/", wait_until="load", timeout=60000)
    page.wait_for_selector(".ag-root", timeout=30000)
    page.wait_for_selector(".ag-cell", timeout=15000)
    rows = page.locator(".ag-center-cols-container .ag-row").count()
    cells = [c.inner_text() for c in page.locator(".ag-cell").all()[:9]]
    print(f"rows={rows} first_cells={cells}")
    # sort by age header
    page.locator(".ag-header-cell-label", has_text="Age").first.click()
    page.wait_for_timeout(700)
    first_age = page.locator(".ag-cell[col-id='age']").first.inner_text()
    print(f"first_age_after_sort={first_age}")
    if EXPECT_LAMBDA:
        fancy = page.locator(".ag-cell[col-id='fancy'] p, .ag-cell[col-id='fancy']")
        print(f"lambda_col_present={fancy.count() > 0} text={fancy.first.inner_text() if fancy.count() else None}")
    toasts = page.locator("[data-sonner-toast], [role='alert']")
    toast_texts = [t.inner_text()[:200] for t in toasts.all()[:3]]
    print(f"toasts={toast_texts}")
    page.screenshot(path=SHOT)
    interesting = [
        (t, x)
        for t, x in console
        if t in ("error", "warning")
        and "AG Grid Enterprise License" not in x
        and "License Key Not Found" not in x
        and not x.startswith("*")
    ]
    print("console_err_warn=", interesting[:5])
    print("pageerrors=", errors[:3])
    browser.close()
print("OK")
