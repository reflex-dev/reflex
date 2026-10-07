"""Drive the stor app: initial values, change all, browser storage contents, new tab (same browser storage, new token), reload.

Usage: NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python drive_stor.py <base> <out.json>
"""

import json
import sys
import time

from playwright.sync_api import sync_playwright

base, out = sys.argv[1].rstrip("/"), sys.argv[2]
IDS = ["a_plain", "b_facplain", "c_facls", "d_lsval", "e_ctrl", "f_ck_plain", "g_ck_lsval", "cs_value"]
res, console = {}, []


def vals(pg):
    return {k: pg.inner_text(f"#{k}", timeout=5000) for k in IDS}


def storage(pg):
    return pg.evaluate("() => { const o = {}; for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i); o[k] = localStorage.getItem(k); } return {local: o, cookie: document.cookie}; }")


def open_page(ctx, tag):
    pg = ctx.new_page()
    pg.on("console", lambda m: console.append(f"[{tag}] {m.type}: {m.text[:300]}"))
    pg.on("pageerror", lambda e: console.append(f"[{tag}] PAGEERROR: {str(e)[:300]}"))
    pg.goto(base + "/", wait_until="networkidle", timeout=180000)
    pg.wait_for_function("() => !!window.sessionStorage.getItem('token')", timeout=60000)
    pg.wait_for_selector("#cs_value", timeout=60000)
    time.sleep(2.5)
    return pg


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = browser.new_context()
    pg = open_page(ctx, "tab1")
    res["0_initial"] = vals(pg)
    res["0_storage"] = storage(pg)
    pg.click("#change")
    pg.click("#cs_change")
    time.sleep(2.5)
    res["1_after_change"] = vals(pg)
    res["1_storage"] = storage(pg)
    pg2 = open_page(ctx, "tab2")
    res["2_new_tab_same_browser"] = vals(pg2)
    pg2.close()
    pg.reload(wait_until="networkidle")
    time.sleep(2.5)
    res["3_reload_tab1_same_token"] = vals(pg)
    browser.close()
res["persisted_in_new_tab"] = {k: res["2_new_tab_same_browser"][k].startswith("changed") for k in IDS}
res["console"] = [c for c in console if "Hey developer" not in c and "vite" not in c.lower() and "DevTools" not in c]
open(out, "w").write(json.dumps(res, indent=1))
print(json.dumps(res, indent=1))
