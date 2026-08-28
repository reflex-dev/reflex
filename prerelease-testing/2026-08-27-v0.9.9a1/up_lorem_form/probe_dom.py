import sys, time
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = b.new_page()
    page.goto(sys.argv[1], wait_until="load")
    page.get_by_role("button", name="New Task").wait_for(timeout=30000)
    page.get_by_role("button", name="New Task").click()
    time.sleep(2)
    html = page.evaluate("() => document.querySelector('.rt-ProgressRoot').closest('div').parentElement.parentElement.outerHTML")
    print(html[:2000])
    b.close()
