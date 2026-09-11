import sys, time
from playwright.sync_api import sync_playwright
url = sys.argv[1]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_context().new_page()
    pg.on("console", lambda m: print("CONSOLE", m.type, m.text[:200]))
    pg.goto(url, wait_until="networkidle")
    pg.wait_for_timeout(1500)
    pg.get_by_role("button", name="➕ New Task").click()
    pg.wait_for_timeout(2500)
    pg.get_by_role("button", name="➕ New Task").click()
    pg.wait_for_timeout(2500)
    html = pg.content()
    open(sys.argv[2], "w").write(html)
    print("BODY TEXT:", pg.inner_text("body")[:800])
    b.close()
