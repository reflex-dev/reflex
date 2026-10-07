"""Dump a trimmed outerHTML of a page region for selector design. Usage: dump_dom.py <url> <css> [maxlen]"""
import sys

from playwright.sync_api import sync_playwright

url, css = sys.argv[1], sys.argv[2]
n = int(sys.argv[3]) if len(sys.argv) > 3 else 6000
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page(viewport={"width": 1400, "height": 900})
    pg.goto(url, wait_until="networkidle")
    pg.wait_for_timeout(3000)
    print(pg.locator(css).first.evaluate("e => e.outerHTML")[:n])
    b.close()
