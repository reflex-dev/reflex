import sys, time
from playwright.sync_api import sync_playwright
base, user, pw, form_id, out = sys.argv[1].rstrip("/")+"/", sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_context().new_page(); pg.set_default_timeout(20000)
    pg.goto(base+"login", wait_until="networkidle")
    pg.locator("id=username").fill(user); pg.locator("id=password").fill(pw)
    t=time.time(); pg.get_by_role("button", name="Sign in").click()
    for _ in range(60):
        if "/login" not in pg.url: break
        pg.wait_for_timeout(500)
    print("login landed at", pg.url, "after %.1fs" % (time.time()-t))
    pg.goto(base+f"edit/form/{form_id}/", wait_until="networkidle"); pg.wait_for_timeout(1500)
    pg.get_by_text("Your name (Name)").click()
    pg.wait_for_timeout(2000)
    print("url", pg.url)
    html = pg.locator("div[role='dialog']").first.inner_html()
    open(out,"w").write(html)
    print("dialog count", pg.locator("div[role='dialog']").count())
    print("checkbox count", pg.locator("div[role='dialog']").first.get_by_role("checkbox").count())
    b.close()
