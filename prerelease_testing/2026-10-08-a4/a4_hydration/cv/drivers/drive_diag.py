"""Click the cvstore index 'diag' button; print the backend worker's pid/seed/set order."""
import sys

from playwright.sync_api import sync_playwright

assert "/scratchpad/envs/driver/" in sys.executable, sys.executable
BASE = sys.argv[1].rstrip("/")
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = b.new_page()
    page.goto(BASE + "/", wait_until="networkidle")
    page.wait_for_function("document.querySelector('#hyd')?.innerText === 'hydrated'", timeout=20000)
    page.click("#diag")
    page.wait_for_selector("#diag_info:has-text('pid=')", timeout=10000)
    print("DIAG", page.locator("#version").inner_text(), "|", page.locator("#diag_info").inner_text())
    b.close()
