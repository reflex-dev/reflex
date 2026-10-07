"""Focused probe of /model-ssrm: data requests/responses and rendered rows around login, generate and reload.

Usage: probe_ssrm.py <base_url> <out_png_prefix>
"""
import json
import sys
import time

from playwright.sync_api import sync_playwright

base, out = sys.argv[1].rstrip("/"), sys.argv[2]
log = []


def rows(p):
    return p.evaluate("""() => [...document.querySelectorAll('.ag-row .ag-cell[col-id="name"]')].map(c => c.innerText.trim())""")


with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    p = b.new_context().new_page()
    p.on("response", lambda r: log.append(f"{time.strftime('%X')} {r.status} {r.url[:160]}") if "abstract-wrapper-data" in r.url else None)
    p.on("console", lambda m: log.append(f"console {m.type}: {m.text[:200]}") if m.type in ("error", "warning") else None)
    p.on("pageerror", lambda e: log.append(f"PAGEERROR {e}"))
    p.goto(base + "/model-ssrm", wait_until="networkidle")
    time.sleep(3)
    print("logged-out rows:", rows(p))
    if p.locator("button:has-text('Login')").count():
        p.click("button:has-text('Login')")
        time.sleep(3)
    print("after login rows:", len(rows(p)), rows(p)[:3])
    p.screenshot(path=f"{out}-1-login.png")
    p.reload(wait_until="networkidle")
    for i in range(20):
        time.sleep(1)
        if rows(p):
            break
    print(f"after reload ({i+1}s) rows:", len(rows(p)), rows(p)[:3])
    print("buttons:", p.locator("button").all_inner_texts()[:10])
    p.screenshot(path=f"{out}-2-reload.png")
    b.close()
print("\n".join(log))
