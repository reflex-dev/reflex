"""Walk the dashboard template's pages (direct + client nav) and exercise the table page.

Usage: driver-python drive_template.py <frontend_url> <out_dir> <label>
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from pwkit import CHROMIUM, Sink, expect, summarize

base, out, label = sys.argv[1].rstrip("/"), Path(sys.argv[2]), sys.argv[3]
out.mkdir(parents=True, exist_ok=True)
sink = Sink()
routes = ["/", "/table", "/profile", "/settings", "/about"]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROMIUM)
    page = b.new_page(viewport={"width": 1400, "height": 1000})
    sink.attach(page, "t1")
    for r in routes:
        def visit(r=r):
            page.goto(base + r, wait_until="networkidle", timeout=120000)
            page.wait_for_timeout(1200)
            body = page.locator("body").inner_text()
            page.screenshot(path=str(out / f"{label}{r.replace('/', '_') or '_index'}.png"))
            return expect(len(body) > 50 and "Error" not in body[:200], body[:120].replace("\n", " "))
        sink.check(f"direct load {r}", visit)

    def table():
        page.goto(base + "/table", wait_until="networkidle")
        page.wait_for_selector("table tbody tr", timeout=30000)
        n0 = page.locator("table tbody tr").count()
        first0 = page.locator("table tbody tr").first.inner_text()
        page.locator("input[placeholder*='Search' i]").first.fill("a")
        page.wait_for_timeout(800)
        page.locator("table thead th, table thead td").nth(1).click()
        page.wait_for_timeout(800)
        return expect(n0 > 0, f"rows={n0} first_row={first0[:80]!r}")

    sink.check("table page renders rows + search/sort interaction", table)

    def client_nav():
        page.goto(base + "/", wait_until="networkidle")
        links = page.locator("a[href='/about']:visible")
        links.first.click()
        page.wait_for_url("**/about", timeout=15000)
        return page.url

    sink.check("client nav via sidebar link", client_nav)
    b.close()
report = sink.dump(out / f"{label}-report.json", label=label)
print(summarize(report))
