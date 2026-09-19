"""Two tabs sharing one reflex client token: does an uncached computed var whose
value changed while tab B was not listening ever reach tab B?

Usage: python twotab_uncached.py <frontend_port> <label>
Requires the authapp (apps/authapp) running on that port.
"""
import json, sys
from playwright.sync_api import sync_playwright

PORT = int(sys.argv[1]); LABEL = sys.argv[2]
BASE = f"http://localhost:{PORT}"
OUT = {"label": LABEL, "steps": [], "console": [], "pageerrors": []}

def rec(name, **kw):
    OUT["steps"].append({"step": name, **kw}); print(f"[{name}] " + json.dumps(kw, default=str)[:400], flush=True)

def t(page, sel):
    try: return page.locator(sel).first.inner_text(timeout=4000)
    except Exception as e: return f"<absent:{type(e).__name__}>"

def snap(page, tag):
    return {"hits": t(page, "#hits"), "note_echo": t(page, "#note-echo"), "raw": t(page, "#secret-note")}

with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
    ctx = br.new_context()
    a = ctx.new_page(); b = ctx.new_page()
    for pg in (a, b):
        pg.on("console", lambda m: OUT["console"].append({"type": m.type, "text": m.text[:200]}))
        pg.on("pageerror", lambda e: OUT["pageerrors"].append(str(e)[:300]))
    a.goto(BASE, wait_until="networkidle"); a.wait_for_timeout(2000)
    b.goto(BASE, wait_until="networkidle"); b.wait_for_timeout(2000)
    tok_a = a.evaluate("() => localStorage.getItem('token') || sessionStorage.getItem('token')")
    tok_b = b.evaluate("() => localStorage.getItem('token') || sessionStorage.getItem('token')")
    rec("tokens", a=tok_a, b=tok_b, same=(tok_a == tok_b))
    rec("initial_a", **snap(a, "a")); rec("initial_b", **snap(b, "b"))
    # tab A changes the value backing the uncached var note_echo
    a.click("#poison-field"); a.wait_for_timeout(1500)
    rec("after_poison_a", **snap(a, "a")); rec("after_poison_b", **snap(b, "b"))
    # tab B now fires its own (unrelated) event -> does it learn the new value?
    b.click("#bump"); b.wait_for_timeout(1500)
    rec("b_after_own_event", **snap(b, "b"))
    b.click("#bump"); b.wait_for_timeout(1500)
    rec("b_after_second_event", **snap(b, "b"))
    b.reload(wait_until="networkidle"); b.wait_for_timeout(2000)
    rec("b_after_reload", **snap(b, "b"))
    br.close()
import os
path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", f"twotab_{LABEL}.json")
json.dump(OUT, open(path, "w"), indent=1)
print("wrote", path)
