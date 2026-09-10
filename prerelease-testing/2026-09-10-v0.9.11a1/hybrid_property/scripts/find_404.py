"""Pin down the URL behind the prod-mode console error 'Failed to load resource: 404'."""
import sys
from playwright.sync_api import sync_playwright
base = sys.argv[1].rstrip("/")
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context(); page = ctx.new_page()
    ctx.on("response", lambda r: print("CTX RESP", r.status, r.request.resource_type, r.url) if r.status >= 400 else None)
    ctx.on("requestfailed", lambda r: print("CTX FAILED", r.url, r.failure))
    page.on("console", lambda m: print("CONSOLE", m.type, m.text[:120], m.location) if m.type in ("error", "warning") else None)
    cdp = ctx.new_cdp_session(page); cdp.send("Network.enable")
    cdp.on("Network.responseReceived", lambda e: print("CDP RESP", e["response"]["status"], e["type"], e["response"]["url"]) if e["response"]["status"] >= 400 else None)
    for path in ("/", "/inherit", "/dc"):
        page.goto(base + path); page.wait_for_timeout(2500)
    b.close()
print("done")
