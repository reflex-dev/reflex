"""Reconnect a browser using a client token whose state was pickled by 0.9.11.post1."""
import json, sys, time
from playwright.sync_api import sync_playwright

BASE = sys.argv[1]
OLD_TOKEN = sys.argv[2]
OUT = sys.argv[3]

console, errs, bad = [], [], []
frames = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    pg = ctx.new_page()
    pg.on("console", lambda m: console.append((m.type, m.text[:300])))
    pg.on("pageerror", lambda e: errs.append(str(e)[:400]))
    pg.on("response", lambda r: bad.append((r.status, r.url)) if r.status >= 400 else None)
    pg.on("websocket", lambda ws: (ws.on("framereceived", lambda x: frames.append(("recv", x[:900]))),
                                   ws.on("framesent", lambda x: frames.append(("sent", x[:900])))))
    pg.goto(BASE + "/", wait_until="networkidle")
    pg.wait_for_timeout(2000)
    # discover where the token lives
    storage = pg.evaluate("() => ({local: Object.fromEntries(Object.entries(localStorage)), session: Object.fromEntries(Object.entries(sessionStorage))})")
    print("STORAGE BEFORE:", json.dumps(storage)[:800])
    # overwrite every entry that looks like a uuid token with the old one
    n = pg.evaluate(
        """(tok) => { let n=0;
             for (const s of [localStorage, sessionStorage]) {
               for (const k of Object.keys(s)) {
                 if (/^[0-9a-f-]{30,40}$/i.test(s.getItem(k))) { s.setItem(k, tok); n++; }
               }
             }
             return n; }""", OLD_TOKEN)
    print("overwrote", n, "token entries with", OLD_TOKEN)
    frames.clear(); console.clear(); errs.clear(); bad.clear()
    pg.goto(BASE + "/items/55", wait_until="networkidle")
    pg.wait_for_timeout(3000)
    storage2 = pg.evaluate("() => ({local: Object.fromEntries(Object.entries(localStorage)), session: Object.fromEntries(Object.entries(sessionStorage))})")
    print("STORAGE AFTER:", json.dumps(storage2)[:800])
    for i in ["page_title","cv_auto_path","cv_deps_whole_router","cv_session","cv_page_params","item_loaded_id","counter"]:
        el = pg.query_selector("#" + i)
        print(f"  {i} = {el.inner_text() if el else None}")
    pg.screenshot(path=OUT + "/redis_upgrade.png")
    pg.click("#btn_bump"); pg.wait_for_timeout(1200)
    el = pg.query_selector("#counter"); print("  counter after bump =", el.inner_text() if el else None)
    pg.click("#nav_search"); pg.wait_for_timeout(1500)
    for i in ["cv_auto_path","cv_query_params","search_q"]:
        el = pg.query_selector("#" + i); print(f"  after nav {i} = {el.inner_text() if el else None}")
    pg.screenshot(path=OUT + "/redis_upgrade_after_nav.png")
    b.close()

print("CONSOLE:", [c for c in console if c[0] in ("error","warning")])
print("PAGEERRORS:", errs)
print("BAD:", bad)
open(OUT + "/redis_upgrade_frames.txt","w").write("\n".join(f"{d}: {x}" for d,x in frames))
