"""Print every >=400 response for a URL list (to attribute console 404s)."""
import sys
from playwright.sync_api import sync_playwright
from pwkit import CHROMIUM
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROMIUM)
    page = b.new_page()
    page.on("response", lambda r: print(r.status, r.url) if r.status >= 400 else None)
    for u in sys.argv[1:]:
        page.goto(u, wait_until="networkidle")
        page.wait_for_timeout(1500)
    b.close()
