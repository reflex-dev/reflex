"""Print every console message / page error / failed request for one page load. Usage: dbg_console.py URL [wait_s]"""
import sys, time
import playwright
assert "/envs/driver/" in playwright.__file__
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = br.new_page()
    pg.on("console", lambda m: print("CONSOLE", m.type, m.text[:600]))
    pg.on("pageerror", lambda e: print("PAGEERROR", str(e)[:800]))
    pg.on("requestfailed", lambda r: print("REQFAILED", r.url, r.failure))
    pg.on("response", lambda r: r.status >= 400 and print("HTTP", r.status, r.url))
    pg.goto(sys.argv[1]); time.sleep(float(sys.argv[2]) if len(sys.argv) > 2 else 4)
    print("BODY", pg.inner_text("body")[:300].replace("\n", " | "))
    br.close()
