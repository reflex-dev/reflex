"""Log in via /login/ (trailing slash) vs /login and report where the app lands.

usage: probe_login_slash.py <frontend_url> <user> <password> <slash|noslash> <screenshot_path>
reflex_local_auth's LoginState.redir compares router.url.path with LOGIN_ROUTE ("/login"),
so a trailing slash makes the post-login redirect a no-op even though the session is valid.
"""
import sys
from playwright.sync_api import sync_playwright

base, user, pw, variant, shot = (
    sys.argv[1].rstrip("/") + "/", sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context(); pg = ctx.new_page(); pg.set_default_timeout(20000)
    target = base + ("login/" if variant == "slash" else "login")
    pg.goto(target, wait_until="networkidle")
    print("after goto:", pg.evaluate("() => location.href"))
    pg.locator("id=username").fill(user)
    pg.locator("id=password").fill(pw)
    pg.get_by_role("button", name="Sign in").click()
    for _ in range(80):          # up to 20s, pumping the event loop
        if "/login" not in pg.evaluate("() => location.href"):
            break
        pg.wait_for_timeout(250)
    print("after login:", pg.evaluate("() => location.href"))
    pg.goto(base, wait_until="networkidle"); pg.wait_for_timeout(1200)
    pg.locator(".lucide-menu").click(); pg.wait_for_timeout(800)
    print("session_authenticated:", user in pg.inner_text("body"))
    pg.screenshot(path=shot)
    b.close()
