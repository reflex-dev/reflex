import sys, time, json
from playwright.sync_api import sync_playwright
BASE=sys.argv[1]
out=sys.argv[2]
msgs=[]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg=b.new_page()
    pg.on("console", lambda m: msgs.append((m.type, m.text[:500])))
    pg.on("pageerror", lambda e: msgs.append(("pageerror", str(e)[:800])))
    pg.goto(BASE, wait_until="load")
    time.sleep(6)
    pg.screenshot(path=out+"/diag.png", full_page=False)
    print("TITLE", pg.title())
    print("BODYLEN", len(pg.content()))
    print(pg.evaluate("() => document.body.innerText.slice(0,1500)"))
    print("RENDERS", json.dumps(pg.evaluate("() => window.__renders || null")))
    b.close()
for t,m in msgs:
    print(t.upper(), m)
