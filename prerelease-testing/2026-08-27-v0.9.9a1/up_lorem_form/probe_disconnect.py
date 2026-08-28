"""Start 2 streaming tasks then abruptly close the browser mid-stream.

Checks how the server handles delivering deltas to a disconnected client.
"""
import sys, time
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = b.new_page()
    page.goto(sys.argv[1], wait_until="load")
    btn = page.get_by_role("button", name="New Task")
    btn.wait_for(timeout=30000)
    btn.click(); time.sleep(0.3); btn.click()
    time.sleep(1.5)  # tasks are mid-stream now
    b.close()  # abrupt disconnect while background tasks still running
print("browser closed mid-stream")
