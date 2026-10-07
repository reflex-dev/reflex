"""Drive apps/clse2e: initial, change, browser storage + cookie attributes, cross-tab sync, new tab, reload.
Usage: NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python drive_clse2e.py <base> <out.json>"""
import json
import sys
import time

from playwright.sync_api import sync_playwright

assert "/envs/driver/" in sys.executable, sys.executable
base, out = sys.argv[1].rstrip("/"), sys.argv[2]
IDS = ["sync", "ck", "ann", "ss", "opt"]
res, console, bad = {}, [], []


def vals(p):
    return {k: p.inner_text(f"#v_{k}", timeout=5000) for k in IDS}


def store(p, ctx):
    js = "() => ({local: Object.fromEntries(Object.entries(localStorage).filter(([k]) => k.startsWith('k_'))), session: Object.fromEntries(Object.entries(sessionStorage).filter(([k]) => k.startsWith('k_')))})"
    d = p.evaluate(js)
    d["cookies"] = [{k: c[k] for k in ("name", "value", "path", "sameSite", "expires")} for c in ctx.cookies() if c["name"].startswith("k_")]
    for c in d["cookies"]:
        c["expires_in_s"] = round(c.pop("expires") - time.time()) if c["expires"] > 0 else "session"
    return d


def open_page(ctx, tag):
    p = ctx.new_page()
    p.on("console", lambda m: console.append(f"[{tag}] {m.type}: {m.text[:300]}"))
    p.on("pageerror", lambda e: console.append(f"[{tag}] PAGEERROR: {str(e)[:300]}"))
    p.on("response", lambda r: bad.append(f"[{tag}] {r.status} {r.url}") if r.status >= 400 else None)
    p.goto(base + "/", wait_until="networkidle", timeout=180000)
    p.wait_for_function("() => document.querySelector('#hyd')?.textContent === 'H:yes'", timeout=60000)
    time.sleep(1.5)
    return p


with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    p1 = open_page(ctx, "tab1")
    res["outcomes"] = p1.inner_text("#outcomes")
    res["0_initial"] = vals(p1)
    res["0_store"] = store(p1, ctx)
    p1.click("#change_a")
    time.sleep(2)
    res["1_after_change"] = vals(p1)
    res["1_store"] = store(p1, ctx)
    p2 = open_page(ctx, "tab2")
    res["2_new_tab"] = vals(p2)
    p2.click("#set_sync")
    time.sleep(2.5)
    res["3_tab1_after_tab2_set_sync"] = vals(p1)
    res["3_tab2"] = vals(p2)
    p1.reload(wait_until="networkidle")
    p1.wait_for_function("() => document.querySelector('#hyd')?.textContent === 'H:yes'", timeout=60000)
    time.sleep(1.5)
    res["4_tab1_reload"] = vals(p1)
    res["4_store"] = store(p1, ctx)
    p1.screenshot(path=out.replace(".json", ".png"), full_page=True)
    b.close()
res["console"] = [c for c in console if "Hey developer" not in c and "[vite]" not in c and "DevTools" not in c and "Disconnect websocket" not in c]
res["bad"] = bad
open(out, "w").write(json.dumps(res, indent=1))
print(json.dumps(res, indent=1))
