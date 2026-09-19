import json, sys
from playwright.sync_api import sync_playwright
BASE=sys.argv[1]; SHOTS=sys.argv[2]
con=[]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg=b.new_page(); pg.on("console", lambda m: con.append(f"{m.type}: {m.text[:200]}"))
    for route in ("/plain", "/"):
        con.clear()
        pg.goto(BASE+route, wait_until="networkidle", timeout=90000); pg.wait_for_timeout(2500)
        before=pg.locator("#count").first.inner_text()
        pg.click("#inc"); pg.wait_for_timeout(1200)
        after=pg.locator("#count").first.inner_text()
        print(json.dumps({"route":route,"title":pg.title(),"count_before":before,"count_after":after,
                          "console_errors":[c for c in con if c.startswith("error")]}, indent=2))
        pg.screenshot(path=f"{SHOTS}/probe{route.replace('/','_')}.png")
    b.close()
