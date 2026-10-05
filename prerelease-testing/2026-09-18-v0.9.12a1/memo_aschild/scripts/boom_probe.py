import sys, json
from playwright.sync_api import sync_playwright
BASE=sys.argv[1].rstrip("/"); OUT=sys.argv[2]
import os; os.makedirs(OUT, exist_ok=True)
msgs=[]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg=b.new_context().new_page()
    pg.on("console", lambda m: msgs.append({"t":m.type,"x":m.text}))
    # memoapp body
    pg.goto(f"{BASE}/memoapp", wait_until="domcontentloaded"); pg.wait_for_timeout(3500)
    print("MEMOAPP_BODY=" + json.dumps(pg.locator("body").inner_text()[:700]))
    print("MEMOAPP_FILEINPUTS=", pg.locator("input[type=file]").count())
    print("MEMOAPP_CONSOLE_ERR=", json.dumps([m for m in msgs if m["t"]=="error"])[:2500])
    pg.screenshot(path=f"{OUT}/memoapp.png")
    msgs.clear()
    pg.goto(f"{BASE}/boom", wait_until="domcontentloaded"); pg.wait_for_timeout(4000)
    print("BOOM_BODY=" + json.dumps(pg.locator("body").inner_text()[:300]))
    inv=[m for m in msgs if "Invalid DOM property" in m["x"] or "invalid DOM property" in m["x"].lower()]
    print("INVALID_DOM_PROPERTY_COUNT=", len(inv))
    print("INVALID=", json.dumps(inv, indent=1)[:2500])
    print("ALL_WARN_ERR=", json.dumps([m for m in msgs if m["t"] in ("error","warning")])[:3500])
    pg.screenshot(path=f"{OUT}/boom.png")
    b.close()
