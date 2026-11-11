"""Load /factory in N fresh browser contexts. usage: cv_loads.py <base> <n>"""
import sys

from playwright.sync_api import sync_playwright

base, n = sys.argv[1], int(sys.argv[2])
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for i in range(n):
        c = b.new_context()
        pg = c.new_page()
        pg.goto(base + "/factory")
        pg.wait_for_selector("#tok:has-text('tok')", timeout=60000)
        pg.wait_for_timeout(800)
        c.close()
    b.close()
