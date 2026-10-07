"""reverify_hydration: csbox app — fresh load (what is written?), click choose on each box, reload, check
display + localStorage. Usage: csbox_check.py BASE OUT_JSON"""
import json
import sys

from playwright.sync_api import sync_playwright

assert "/envs/driver/" in sys.executable, sys.executable
base, out = sys.argv[1].rstrip("/"), sys.argv[2]
tags = ["none", "plain", "storage"]


def shown(p):
    return {t: p.locator(f"#pref-{t}").inner_text() for t in tags}


def ls(p):
    return p.evaluate("() => Object.fromEntries(Object.entries(localStorage).filter(([k]) => k.startsWith('box')))")


def hyd(p):
    p.wait_for_function("() => document.querySelector('#hyd-flag')?.textContent === 'H:yes'", timeout=30000)
    p.wait_for_timeout(800)


r = {}
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    p = ctx.new_page()
    cons = []
    p.on("console", lambda m: m.type in ("error", "warning") and cons.append(m.text[:200]))
    p.goto(base + "/")
    hyd(p)
    r["first_load"] = {"shown": shown(p), "localStorage": ls(p)}
    for t in tags:
        p.click(f"#choose-{t}")
    p.wait_for_timeout(1000)
    r["after_choose"] = {"shown": shown(p), "localStorage": ls(p)}
    p.reload()
    hyd(p)
    r["after_reload"] = {"shown": shown(p), "localStorage": ls(p)}
    # new tab in the same context: new session token (sessionStorage), same localStorage
    p2 = ctx.new_page()
    p2.goto(base + "/")
    hyd(p2)
    r["new_tab_same_browser"] = {"shown": shown(p2), "localStorage": ls(p2)}
    r["console"] = cons
    b.close()
json.dump(r, open(out, "w"), indent=1)
print(json.dumps(r, indent=1))
