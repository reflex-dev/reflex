"""Load a model-wrapper route, print data requests/statuses, row cells and non-license console errors."""
import sys
import time

from playwright.sync_api import sync_playwright

base, route = sys.argv[1].rstrip("/"), sys.argv[2]
ev = []
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    p = b.new_context().new_page()
    p.on("request", lambda r: ev.append(f"REQ {r.url[:150]}") if "wrapper-data" in r.url else None)
    p.on("response", lambda r: ev.append(f"RESP {r.status} {r.url[:120]}") if "wrapper-data" in r.url or r.status >= 400 else None)
    p.on("console", lambda m: ev.append(f"console {m.type}: {m.text[:300]}") if m.type == "error" and "*" not in m.text[:5] else None)
    p.on("pageerror", lambda e: ev.append(f"PAGEERROR {e}"))
    p.goto(base + route, wait_until="networkidle")
    time.sleep(6)
    cells = p.evaluate("""() => [...document.querySelectorAll('.ag-row .ag-cell[col-id="name"]')].map(c=>c.innerText.trim()).slice(0,5)""")
    nrows = p.evaluate("() => document.querySelectorAll('.ag-row').length")
    print("rows", nrows, "cells", cells)
    b.close()
print("\n".join(ev[:30]))
