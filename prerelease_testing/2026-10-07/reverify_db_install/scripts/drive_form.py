"""Submit formapp's form and print the submitted dict. Usage: driver-python drive_form.py <url>"""
import json
import sys

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = b.new_page()
    page.goto(sys.argv[1], wait_until="networkidle", timeout=120000)
    page.click("#submit")
    page.wait_for_function("document.querySelector('#form-data')?.textContent?.length > 3", timeout=20000)
    data = json.loads(page.locator("#form-data").inner_text())
    print(json.dumps(data, sort_keys=True))
    leaked = sorted(k for k in ("form_id", "form_content_wrapper", "submit") if k in data)
    print("non-control ids submitted:", leaked or "none")
    b.close()
