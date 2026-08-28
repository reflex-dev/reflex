"""Repro B + hard reload: did the bg on_load writes happen server-side at all?

Usage: python drive_reload_check.py <base_url>
"""

import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")


def log_of(page):
    return page.locator("#bg-log").inner_text(timeout=5000)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = browser.new_context().new_page()
    page.goto(BASE + "/other", wait_until="load", timeout=60000)
    page.wait_for_selector("#btn-clear", timeout=15000)
    page.wait_for_timeout(1000)
    page.click("#btn-clear")
    page.wait_for_timeout(500)
    page.click("#lnk-slowbg")
    page.wait_for_function(
        "() => document.querySelector('#bg-log').innerText.includes('load1-start')",
        timeout=10000,
    )
    page.click("#lnk-other")
    page.wait_for_function(
        "() => document.querySelector('#hd').innerText === 'OTHER'", timeout=10000
    )
    page.wait_for_timeout(6000)
    print("after nav+6s (same view):", log_of(page), flush=True)
    # Hard reload: server pushes current state on reconnect/hydrate.
    page.reload(wait_until="load")
    page.wait_for_selector("#bg-log", timeout=15000)
    page.wait_for_timeout(2000)
    print("after hard reload      :", log_of(page), flush=True)
    browser.close()
