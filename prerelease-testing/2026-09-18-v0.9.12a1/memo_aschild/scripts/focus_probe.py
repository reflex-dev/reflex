import sys, json
from playwright.sync_api import sync_playwright
BASE=sys.argv[1].rstrip("/")
msgs=[];errs=[]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg=b.new_context().new_page()
    pg.on("console", lambda m: msgs.append({"t":m.type,"x":m.text}))
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f"{BASE}/forms", wait_until="networkidle"); pg.wait_for_timeout(1800)
    print("HAS_FOCUS_BTN", pg.locator("#btn_focus").count())
    pg.locator("#btn_focus").click(); pg.wait_for_timeout(1200)
    act = pg.evaluate("() => { const a=document.activeElement; return {id:a.id, tag:a.tagName}; }")
    print("ACTIVE_AFTER_SET_FOCUS=", json.dumps(act))
    print("ERRS=", json.dumps(errs)[:1500])
    print("CONSOLE_ERR=", json.dumps([m for m in msgs if m["t"]=="error"])[:2000])
    b.close()
