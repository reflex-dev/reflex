"""Click each form control on a page one at a time and print console warnings/errors after each click.

Usage: NO_PROXY=localhost,127.0.0.1 python isolate_warning.py http://localhost:3100/ [selector ...]
"""
import sys
from playwright.sync_api import sync_playwright
url=sys.argv[1]; sels=sys.argv[2:]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path="/opt/pw-browsers/chromium"); pg=b.new_page()
    msgs=[]; pg.on("console", lambda m: msgs.append((m.type,m.text[:160])) if m.type in("warning","error") else None)
    pg.goto(url, wait_until="networkidle"); pg.wait_for_timeout(1500)
    print("after load:", msgs); msgs.clear()
    for s in sels:
        try: pg.click(s, timeout=5000)
        except Exception as e: print(s, "CLICK FAILED", type(e).__name__); continue
        pg.wait_for_timeout(600); print(repr(s), "->", msgs); msgs.clear()
    b.close()
