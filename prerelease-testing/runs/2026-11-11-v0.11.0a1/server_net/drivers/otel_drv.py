"""Click go, bg, boom on otelapp. usage: otel_drv.py <base>"""
import sys
assert "/envs/driver/" in sys.executable
from playwright.sync_api import sync_playwright
base = sys.argv[1]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    pg.goto(base)
    pg.wait_for_selector("#go")
    pg.wait_for_timeout(1500)
    pg.click("#go"); pg.wait_for_function("document.querySelector('#n').innerText.includes('n=1')", timeout=10000)
    pg.click("#bg"); pg.wait_for_function("document.querySelector('#n').innerText.includes('n=11')", timeout=10000)
    pg.click("#boom"); pg.wait_for_timeout(1500)
    print("driver ok", pg.inner_text("#n"))
    b.close()
