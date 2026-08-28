"""Click the diag buttons and print the resulting status text.

Usage: driver/bin/python drive_diag.py <frontend_url>
"""

import sys

from playwright.sync_api import sync_playwright

url = sys.argv[1]
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = browser.new_page()
    page.goto(url, wait_until="load", timeout=60000)
    page.wait_for_selector("#btn-diag", timeout=30000)
    page.click("#btn-diag")
    page.wait_for_function(
        "document.querySelector('#status').innerText.startsWith('diag|')",
        timeout=15000,
    )
    print("DIAG:", page.inner_text("#status"))
    page.click("#btn-diag2")
    page.wait_for_function(
        "document.querySelector('#status').innerText.startsWith('diag2|')",
        timeout=15000,
    )
    print("DIAG2:", page.inner_text("#status"))
    browser.close()
