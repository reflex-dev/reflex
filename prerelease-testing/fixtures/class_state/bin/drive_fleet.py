"""Drive the fleet app: start a session or resume one by token, record what the server returns on arrival, then login+incr.

Usage: NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python drive_fleet.py <base> <tokfile> <label> new|resume <outjsonl>
Appends one JSON line per phase to <outjsonl>.
"""

import json
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

base, tokfile, label, mode, outp = sys.argv[1].rstrip("/"), Path(sys.argv[2]), sys.argv[3], sys.argv[4], Path(sys.argv[5])
console, bad = [], []


def txt(page, sel):
    try:
        return page.inner_text(sel, timeout=5000)
    except Exception as e:  # noqa: BLE001
        return f"<missing: {type(e).__name__}>"


def snap(page):
    return {k: txt(page, f"#{k}") for k in ("server", "user", "count", "history")}


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ.get("CHROMIUM", "/opt/pw-browsers/chromium"))
    ctx = browser.new_context()
    if mode == "resume":
        tok = tokfile.read_text().strip()
        ctx.add_init_script(f"window.sessionStorage.setItem('token', {json.dumps(tok)});")
    page = ctx.new_page()
    page.on("console", lambda m: console.append(f"{m.type}: {m.text[:300]}"))
    page.on("pageerror", lambda e: console.append(f"PAGEERROR: {str(e)[:300]}"))
    page.on("response", lambda r: bad.append(f"{r.status} {r.url}") if r.status >= 400 else None)
    page.goto(base + "/", wait_until="networkidle", timeout=180000)
    page.wait_for_function("() => !!window.sessionStorage.getItem('token')", timeout=60000)
    page.wait_for_selector("#count", timeout=60000)
    time.sleep(2.5)  # hydration
    tok = page.evaluate("() => sessionStorage.getItem('token')")
    if mode == "new":
        tokfile.write_text(tok)
    rec = {"label": label, "mode": mode, "token": tok, "on_arrival": snap(page)}
    before = rec["on_arrival"]["count"]
    page.click("#login")
    page.click("#incr")
    end = time.time() + 15
    while time.time() < end and txt(page, "#count") == before:
        time.sleep(0.2)
    time.sleep(1.0)
    rec["after_login_incr"] = snap(page)
    browser.close()
rec["console_non_benign"] = [c for c in console if "Hey developer" not in c and "vite" not in c.lower() and "DevTools" not in c]
rec["bad_responses"] = bad
with outp.open("a") as f:
    f.write(json.dumps(rec) + "\n")
print(json.dumps(rec, indent=1))
