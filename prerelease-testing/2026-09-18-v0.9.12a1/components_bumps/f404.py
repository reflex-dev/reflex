import json,sys
from playwright.sync_api import sync_playwright
BASE=sys.argv[1].rstrip("/")
bad=[]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg=b.new_context(viewport={"width":1280,"height":900}).new_page()
    pg.on("response", lambda r: bad.append((r.status, r.url)) if r.status>=400 else None)
    pg.on("requestfailed", lambda r: bad.append(("FAILED", r.url)))
    for path in ["/editor","/code","/misc","/sankey","/plotly","/toast","/props"]:
        pg.goto(f"{BASE}{path}", wait_until="networkidle", timeout=60000); pg.wait_for_timeout(1500)
    b.close()
print(json.dumps(bad, indent=2))
