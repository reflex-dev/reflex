"""Which ways of reaching the login page survive the prod trailing-slash redirect?

usage: drive_paths.py <frontend_url> <label> <outdir>

Registers a user, then in three fresh browser contexts logs in after arriving at the
login page by (a) a hard document load of /login, (b) a client-side rx.redirect from
require_login on /protected, (c) a client-side rx.link click from the index page.
"""

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

base = sys.argv[1].rstrip("/")
label = sys.argv[2]
out = Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
user = f"p{int(time.time())}"
pw = "verify2pw"
res = {"label": label, "base": base, "user": user, "cases": {}}


def login_here(pg, case, out):
    pg.wait_for_timeout(1500)
    rec = {
        "href_on_login_page": pg.evaluate("() => location.href"),
        "router_path": pg.locator("id=routerpath").inner_text(),
        "matches": pg.locator("id=matches").inner_text(),
    }
    pg.locator("id=username").fill(user)
    pg.locator("id=password").fill(pw)
    t0 = time.time()
    pg.get_by_role("button", name="Sign in").click()
    left = False
    while time.time() - t0 < 15:
        if "/login" not in pg.evaluate("() => location.pathname"):
            left = True
            break
        pg.wait_for_timeout(250)
    rec["left_login_page"] = left
    rec["seconds"] = round(time.time() - t0, 1)
    rec["href_after_login"] = pg.evaluate("() => location.href")
    pg.screenshot(path=str(out / f"{case}.png"))
    res["cases"][case] = rec
    print(case, json.dumps(rec))


with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    pg = ctx.new_page()
    pg.set_default_timeout(20000)
    pg.goto(base + "/register", wait_until="networkidle")
    pg.locator("id=username").fill(user)
    pg.locator("id=password").fill(pw)
    pg.locator("id=confirm_password").fill(pw)
    pg.get_by_role("button", name="Sign up").click()
    pg.wait_for_timeout(3000)
    ctx.close()

    # (a) hard document load of /login
    ctx = b.new_context(); pg = ctx.new_page(); pg.set_default_timeout(20000)
    pg.goto(base + "/login", wait_until="networkidle")
    login_here(pg, "a_hard_load_login", out)
    ctx.close()

    # (b) require_login bounce from /protected
    ctx = b.new_context(); pg = ctx.new_page(); pg.set_default_timeout(20000)
    pg.goto(base + "/protected", wait_until="networkidle")
    pg.wait_for_timeout(2500)
    res["cases_b_bounced_to"] = pg.evaluate("() => location.href")
    login_here(pg, "b_require_login_bounce", out)
    ctx.close()

    # (c) client-side rx.link click from the index page
    ctx = b.new_context(); pg = ctx.new_page(); pg.set_default_timeout(20000)
    pg.goto(base + "/", wait_until="networkidle")
    pg.wait_for_timeout(1500)
    pg.locator("id=gologin").click()
    login_here(pg, "c_link_click", out)
    ctx.close()
    b.close()

(out / "results.json").write_text(json.dumps(res, indent=2))
print(json.dumps(res, indent=2))
