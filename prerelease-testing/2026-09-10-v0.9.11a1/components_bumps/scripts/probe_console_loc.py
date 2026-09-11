"""Print console messages with their source location (finds which URL 404s)."""
import sys
from playwright.sync_api import sync_playwright

url = sys.argv[1]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    pg = ctx.new_page()
    pg.on("console", lambda m: print(m.type, "|", m.text[:120], "|", m.location))
    ctx.on("response", lambda r: print("RESP", r.status, r.url) if r.status >= 400 else None)
    pg.goto(url, wait_until="networkidle")
    pg.wait_for_timeout(3000)
    for sel in ["#m-bump", "#m-client-bump", "#m-tz-btn", "#m-locale-btn", "#m-cstate-btn"]:
        try:
            pg.click(sel)
            pg.wait_for_timeout(900)
        except Exception as e:
            print("click fail", sel, e)
    pg.wait_for_timeout(2000)
    b.close()
