import json,sys
from playwright.sync_api import sync_playwright
BASE=sys.argv[1].rstrip("/")
bad=[]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg=b.new_context().new_page()
    pg.on("response", lambda r: bad.append({"url":r.url,"status":r.status}) if r.status>=400 else None)
    pg.on("requestfailed", lambda r: bad.append({"url":r.url,"failed":r.failure}))
    for route in ["/editor","/ids","/"]:
        try:
            pg.goto(BASE+route, wait_until="networkidle", timeout=60000); pg.wait_for_timeout(1200)
        except Exception as e: bad.append({"route":route,"err":str(e)[:120]})
    print(json.dumps(bad, indent=2))
    b.close()
