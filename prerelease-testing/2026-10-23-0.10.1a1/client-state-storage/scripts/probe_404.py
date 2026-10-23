"""Print every request that fails or gets a >=400 response while loading a page.
Usage: NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python probe_404.py http://localhost:3141/
"""
import sys
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = b.new_page()
    page.on("response", lambda r: print("RESP", r.status, r.url) if r.status >= 400 else None)
    page.on("requestfailed", lambda r: print("FAILED", r.url, r.failure))
    page.on("console", lambda m: print("CONSOLE", m.type, m.text[:200], m.location) if m.type in ("error", "warning") else None)
    page.goto(sys.argv[1])
    page.wait_for_timeout(4000)
    b.close()
