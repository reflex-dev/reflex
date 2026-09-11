"""Minimal driver for the prod trailing-slash / reflex-local-auth login repro.

usage: drive_slash.py <frontend_url> <label> <outdir> [slash|noslash]

Registers a fresh user, then logs in via /login (noslash) or /login/ (slash) and
reports: the HTTP status of GET /login, the router.url.path the app reports on the
login page, where the browser ends up after a successful sign-in, and whether the
session is actually authenticated afterwards.
"""

import json
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

base = sys.argv[1].rstrip("/")
label = sys.argv[2]
out = Path(sys.argv[3])
variant = sys.argv[4] if len(sys.argv) > 4 else "noslash"
out.mkdir(parents=True, exist_ok=True)

opener = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),
    type(
        "NoRedirect",
        (urllib.request.HTTPRedirectHandler,),
        {"redirect_request": lambda *a, **k: None},
    )(),
)


def head(path):
    try:
        r = opener.open(urllib.request.Request(base + path, method="GET"))
        return r.status, r.headers.get("Location")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Location")


res = {"label": label, "variant": variant, "base": base}
res["http"] = {p: head(p) for p in ("/", "/login", "/login/", "/protected", "/register")}
print("HTTP:", json.dumps(res["http"]))

user = f"u{int(time.time())}"
pw = "verify2pw"
res["user"] = user
console, bad = [], []

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    pg = ctx.new_page()
    pg.set_default_timeout(20000)
    pg.on("console", lambda m: console.append({"type": m.type, "text": m.text}))
    pg.on(
        "response",
        lambda r: bad.append({"url": r.url, "status": r.status})
        if r.status >= 400
        else None,
    )

    # register
    pg.goto(base + "/register", wait_until="networkidle")
    pg.locator("id=username").fill(user)
    pg.locator("id=password").fill(pw)
    pg.locator("id=confirm_password").fill(pw)
    pg.get_by_role("button", name="Sign up").click()
    for _ in range(60):
        if "/register" not in pg.evaluate("() => location.pathname"):
            break
        pg.wait_for_timeout(250)
    res["after_register_href"] = pg.evaluate("() => location.href")
    pg.screenshot(path=str(out / "01_after_register.png"))

    # login
    target = base + ("/login/" if variant == "slash" else "/login")
    pg.goto(target, wait_until="networkidle")
    pg.wait_for_timeout(1500)
    res["login_page_href"] = pg.evaluate("() => location.href")
    res["login_page_router_path"] = pg.locator("id=routerpath").inner_text()
    res["login_page_matches_LOGIN_ROUTE"] = pg.locator("id=matches").inner_text()
    try:
        res["login_page_route_id"] = pg.locator("id=routeid").inner_text()
        res["login_page_route_id_matches"] = pg.locator("id=routeidmatches").inner_text()
    except Exception as e:  # older build of the app without the route_id probe
        res["login_page_route_id"] = f"n/a: {e}"
    pg.screenshot(path=str(out / "02_login_page.png"))
    print("login page:", res["login_page_href"], res["login_page_router_path"],
          res["login_page_matches_LOGIN_ROUTE"])

    pg.locator("id=username").fill(user)
    pg.locator("id=password").fill(pw)
    t0 = time.time()
    pg.get_by_role("button", name="Sign in").click()
    left = False
    while time.time() - t0 < 20:
        if "/login" not in pg.evaluate("() => location.pathname"):
            left = True
            break
        pg.wait_for_timeout(250)
    res["left_login_page"] = left
    res["seconds_waited"] = round(time.time() - t0, 1)
    res["after_login_href"] = pg.evaluate("() => location.href")
    res["login_error_visible"] = pg.locator("[role=alert]").count() > 0
    res["login_error_text"] = (
        pg.locator("[role=alert]").first.inner_text()
        if res["login_error_visible"]
        else ""
    )
    pg.screenshot(path=str(out / "03_after_login.png"))
    print("after login:", res["after_login_href"], "left =", left,
          "error =", res["login_error_text"])

    # is the session actually valid?
    pg.goto(base + "/", wait_until="networkidle")
    pg.wait_for_timeout(1500)
    res["index_authstatus"] = pg.locator("id=authstatus").inner_text()
    res["index_router_path"] = pg.locator("id=routerpath").inner_text()
    pg.screenshot(path=str(out / "04_index.png"))

    # require_login page
    pg.goto(base + "/protected", wait_until="networkidle")
    pg.wait_for_timeout(1500)
    res["protected_href"] = pg.evaluate("() => location.href")
    res["protected_heading"] = pg.locator("id=heading").inner_text()
    res["protected_router_path"] = pg.locator("id=routerpath").inner_text()
    pg.screenshot(path=str(out / "05_protected.png"))
    print("index auth:", res["index_authstatus"], "| protected:",
          res["protected_href"], res["protected_heading"])
    b.close()

res["console_errors"] = [c for c in console if c["type"] in ("error", "warning")]
res["bad_responses"] = bad
(out / "results.json").write_text(json.dumps(res, indent=2))
print(json.dumps({k: v for k, v in res.items() if k not in ("console_errors", "bad_responses")}, indent=2))
