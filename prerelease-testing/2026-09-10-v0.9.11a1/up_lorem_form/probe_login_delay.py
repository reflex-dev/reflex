"""Replicate the driver's exact pre-login sequence and time the post-login redirect."""
import sys, time
from playwright.sync_api import sync_playwright

base = sys.argv[1].rstrip("/") + "/"
user = "p" + str(int(time.time()) % 1000000)
pw = "foobarbaz43"
shots = sys.argv[2]

def log(*a):
    print("%7.1fs" % (time.time() - T0), *a, flush=True)

T0 = time.time()
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_context().new_page(); pg.set_default_timeout(20000)
    pg.on("console", lambda m: log("CONSOLE", m.type, m.text[:140]))
    pg.on("websocket", lambda ws: (log("WS OPEN", ws.url), ws.on("close", lambda _: log("WS CLOSE", ws.url))))
    pg.goto(base, wait_until="networkidle"); pg.wait_for_timeout(1000)
    pg.get_by_role("link", name="Create or Edit Forms").click()
    for _ in range(40):
        if "/login" in pg.url: break
        pg.wait_for_timeout(250)
    log("gated to", pg.url)
    # register (mismatch, then success)
    pg.goto(base + "register", wait_until="networkidle")
    pg.locator("id=username").fill(user); pg.locator("id=password").fill(pw)
    pg.get_by_role("button", name="Sign up").click()
    pg.wait_for_timeout(1500)
    log("mismatch error:", pg.get_by_text("Passwords do not match").count())
    pg.locator("id=confirm_password").fill(pw)
    pg.get_by_role("button", name="Sign up").click()
    for _ in range(60):
        if "/login" in pg.url: break
        pg.wait_for_timeout(250)
    log("registered ->", pg.url)
    # duplicate registration
    pg.goto(base + "register", wait_until="networkidle")
    pg.locator("id=username").fill(user); pg.locator("id=password").fill(pw); pg.locator("id=confirm_password").fill(pw)
    pg.get_by_role("button", name="Sign up").click()
    pg.wait_for_timeout(2000)
    log("dup error:", pg.get_by_text("is already registered").count(), pg.url)
    # login: wrong then right
    pg.goto(base + "login", wait_until="networkidle")
    pg.locator("id=username").fill(user); pg.locator("id=password").fill("wrong")
    pg.get_by_role("button", name="Sign in").click()
    pg.wait_for_timeout(2500)
    log("bad login error:", pg.get_by_text("There was a problem logging in").count(), pg.url)
    pg.locator("id=password").fill(pw)
    t = time.time(); pg.get_by_role("button", name="Sign in").click()
    log("clicked sign-in")
    last = pg.url
    for i in range(240):
        if pg.url != last:
            log("URL ->", pg.url)
            last = pg.url
        if "/login" not in pg.url:
            break
        pg.wait_for_timeout(250)
    log("landed", pg.url, "after %.1fs" % (time.time() - t))
    pg.screenshot(path=shots + "/probe_login_delay.png")
    b.close()
