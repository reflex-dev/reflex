"""List every >=400 response and console error per route.  Usage: find404.py <base> <route,...>"""
import sys
import time

from playwright.sync_api import sync_playwright

base, routes = sys.argv[1].rstrip("/"), sys.argv[2].split(",")
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for r in routes:
        pg = b.new_context().new_page()
        ev = []
        pg.on("response", lambda x: ev.append(f"{x.status} {x.url}") if x.status >= 400 else None)
        pg.on("requestfailed", lambda x: ev.append(f"FAILED {x.url} {x.failure}"))
        pg.on("console", lambda m: ev.append(f"console {m.type}: {m.text[:200]} @ {m.location.get('url')}") if m.type in ("error", "warning") else None)
        pg.goto(base + r, wait_until="networkidle")
        time.sleep(2)
        print(r, ev)
    b.close()
