"""Drive the minimal rxe.ag_grid app on 0.9.9a2 (FINDING-021 re-verification).

Checks: grid renders, sort works, and the lambda cell_renderer column ("fancy")
shows custom-rendered <p> cells with the tomato color from rx.text(..., color="tomato").

Usage: python drive_minimal_a2.py <base_url> <shot_path>
"""

import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
SHOT = sys.argv[2]

failures = []

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
    print(f"rows={rows}")
    if rows != 3:
        failures.append(f"expected 3 rows, got {rows}")

    page.locator(".ag-header-cell-label", has_text="Age").first.click()
    # AG Grid repositions rows via transforms without reordering the DOM, so read
    # the visually-first row via row-index="0" rather than DOM order.
    top_age = ".ag-center-cols-container .ag-row[row-index='0'] .ag-cell[col-id='age']"
    first_age = None
    for _ in range(20):  # poll up to 10s for the row reorder
        page.wait_for_timeout(500)
        first_age = page.locator(top_age).first.inner_text()
        if first_age == "25":
            break
    print(f"first_age_after_sort={first_age}")
    if first_age != "25":
        failures.append(f"sort broken: first age {first_age!r} != '25'")

    fancy_p = page.locator(".ag-cell[col-id='fancy'] p")
    page.wait_for_timeout(300)
    n = fancy_p.count()
    texts = [fancy_p.nth(i).inner_text() for i in range(n)]
    colors = [
        fancy_p.nth(i).evaluate("el => getComputedStyle(el).color") for i in range(n)
    ]
    print(f"lambda_cells={n} texts={texts} colors={colors}")
    if n != 3:
        failures.append(f"expected 3 lambda-rendered <p> cells, got {n}")
    # 0.9.8 baseline renders the same quoted form ("John" etc.) — accept it.
    if {t.strip('"') for t in texts} != {"John", "Anna", "Mike"}:
        failures.append(f"lambda cell texts wrong: {texts}")
    if any(c != "rgb(255, 99, 71)" for c in colors):
        failures.append(f"tomato color not applied: {colors}")

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
    if errors:
        failures.append(f"page errors: {errors[:2]}")
    browser.close()

if failures:
    print("RESULT FAIL:", failures)
    sys.exit(1)
print("RESULT PASS: grid + lambda cell_renderer render end-to-end")
