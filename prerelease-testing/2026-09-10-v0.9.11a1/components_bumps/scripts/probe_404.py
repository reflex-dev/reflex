"""Log every request/response on a page load to find 404s."""
import sys
from playwright.sync_api import sync_playwright

url = sys.argv[1]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    bad = []
    pg.on("response", lambda r: bad.append(f"{r.status} {r.request.resource_type} {r.url}") if r.status >= 400 else None)
    pg.on("requestfailed", lambda r: bad.append(f"FAILED {r.url} {r.failure}"))
    pg.goto(url, wait_until="networkidle")
    pg.wait_for_timeout(4000)
    print("bad:", bad)
    b.close()
