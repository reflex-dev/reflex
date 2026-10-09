"""Drive reflex-local-auth's upstream demo (+ tp_extra pages) end to end.

Usage: drive_local_auth.py <base_url> <out_dir> <label>
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

from tpdrive import Capture, browser, safe, wait_text, wait_url

BASE = sys.argv[1].rstrip("/")
OUT = Path(sys.argv[2])
LABEL = sys.argv[3]
DB = sys.argv[4] if len(sys.argv) > 4 else None
OUT.mkdir(parents=True, exist_ok=True)
SUF = str(int(time.time()))[-6:]
U1, U2, U3, U4 = f"alice{SUF}", f"bob{SUF}", f"short{SUF}", f"carol{SUF}"
PW = "correct-horse-1"
cap = Capture(ws_frames=False)


def shot(page, name):
    page.screenshot(path=str(OUT / f"{LABEL}-{name}.png"), full_page=True)


def fill_form(page, values: dict, submit_text: str):
    for k, v in values.items():
        page.fill(f"input#{k}", v)
    page.get_by_role("button", name=submit_text).click()


with browser() as b:
    ctx = b.new_context()
    page = cap.attach(ctx.new_page(), "main")

    cap.label = "index"
    page.goto(BASE + "/", wait_until="networkidle")
    cap.check("index heading", "Welcome to my homepage!" in wait_text(page, "h1, h2", "Welcome"), page.url)
    cap.check("index shows Login link when anonymous", "Login" in wait_text(page, "body", r"\bLogin\b"))

    cap.label = "need2login-anon"
    page.goto(BASE + "/need2login", wait_until="networkidle")
    cap.check("require_login redirects anonymous to /login", "/login" in wait_url(page, r"/login"), page.url)
    shot(page, "01-login-redirect")

    cap.label = "register"
    safe(cap, "register click", lambda: page.get_by_role("link", name="Register").click())
    cap.check("register page reached", "/register" in wait_url(page, r"/register"), page.url)
    page.wait_for_selector("input#username")
    fill_form(page, {"username": U1, "password": PW, "confirm_password": PW + "x"}, "Sign up")
    cap.check("password mismatch error", "Passwords do not match" in wait_text(page, "[role=alert]", "Passwords do not match"))
    fill_form(page, {"username": U1, "password": PW, "confirm_password": PW}, "Sign up")
    cap.check("registration success message", "Registration successful" in wait_text(page, "body", "Registration successful"))
    cap.check("redirected to /login after registration", "/login" in wait_url(page, r"/login", 10))
    shot(page, "02-after-register")

    cap.label = "register-dup"
    page.goto(BASE + "/register", wait_until="networkidle")
    page.wait_for_selector("input#username")
    fill_form(page, {"username": U1, "password": PW, "confirm_password": PW}, "Sign up")
    cap.check("duplicate username rejected", "already registered" in wait_text(page, "[role=alert]", "already registered"))

    cap.label = "login-bad"
    page.goto(BASE + "/need2login", wait_until="networkidle")
    wait_url(page, r"/login")
    page.wait_for_selector("input#username")
    fill_form(page, {"username": U1, "password": "wrong"}, "Sign in")
    cap.check("bad password error", "problem logging in" in wait_text(page, "[role=alert]", "problem logging in"))

    cap.label = "login-good"
    fill_form(page, {"username": U1, "password": PW}, "Sign in")
    cap.check("login redirects back to /need2login (redirect_to)", "/need2login" in wait_url(page, r"/need2login"), page.url)
    cap.check("protected content visible", "Accessing this page" in wait_text(page, "body", "Accessing this page"))
    cap.check("Logout link visible when authenticated", page.get_by_role("link", name="Logout").count() >= 1)
    shot(page, "03-logged-in")

    cap.label = "protected"
    page.goto(BASE + "/protected", wait_until="networkidle")
    cap.check("ProtectedState.on_load data", f"truly private data for {U1}" in wait_text(page, "body", f"private data for {U1}"))

    cap.label = "user-info"
    page.goto(BASE + "/user-info", wait_until="networkidle")
    t = wait_text(page, "body", f"Username: {U1}")
    cap.check("user-info username", f"Username: {U1}" in t, t[:200])
    cap.check("user-info without extra info", "No extra UserInfo for" in t, t[:300])

    cap.label = "reload"
    page.reload(wait_until="networkidle")
    cap.check("still logged in after reload", f"Username: {U1}" in wait_text(page, "body", f"Username: {U1}"))

    cap.label = "second-tab"
    page2 = cap.attach(ctx.new_page(), "tab2")
    page2.goto(BASE + "/protected", wait_until="networkidle")
    cap.check("second tab (same context) shares login", f"private data for {U1}" in wait_text(page2, "body", f"private data for {U1}"))

    cap.label = "fresh-context"
    ctx_b = b.new_context()
    pb = cap.attach(ctx_b.new_page(), "ctxB")
    pb.goto(BASE + "/protected", wait_until="networkidle")
    cap.check("fresh context is anonymous -> /login", "/login" in wait_url(pb, r"/login"), pb.url)
    ctx_b.close()

    cap.label = "logout"
    page.goto(BASE + "/need2login", wait_until="networkidle")
    wait_text(page, "body", "Accessing this page")
    page.get_by_role("link", name="Logout").first.click()
    cap.check("after logout index shows Login link", "Login" in wait_text(page, "body", r"\bLogin\b"))
    page.goto(BASE + "/protected", wait_until="networkidle")
    cap.check("after logout /protected -> /login", "/login" in wait_url(page, r"/login"), page.url)
    page2.reload(wait_until="networkidle")
    cap.check("second tab logged out after reload", "/login" in wait_url(page2, r"/login"), page2.url)
    page2.close()
    shot(page, "04-after-logout")

    cap.label = "custom-register"
    page.goto(BASE + "/custom-register", wait_until="networkidle")
    page.wait_for_selector("input#username")
    fill_form(page, {"username": U2, "email": f"{U2}@example.com", "password": PW, "confirm_password": PW}, "Sign up")
    cap.check("custom registration success", "Registration successful" in wait_text(page, "body", "Registration successful"))
    wait_url(page, r"/login", 10)
    page.wait_for_selector("input#username")
    fill_form(page, {"username": U2, "password": PW}, "Sign in")
    page.wait_for_timeout(1000)
    page.goto(BASE + "/user-info", wait_until="networkidle")
    t = wait_text(page, "body", f"Email: {U2}@example.com")
    cap.check("custom user info email", f"Email: {U2}@example.com" in t, t[:300])
    cap.check("custom user info created_from_ip", "Account Created From:" in t, t[:300])
    shot(page, "05-user-info-custom")

    cap.label = "whoami"
    page.goto(BASE + "/tp-whoami", wait_until="networkidle")
    cap.check("whoami LoginState sees parent computed var", U2 in wait_text(page, "#login_state_user", U2))
    cap.check("whoami MyLocalAuthState sees user", U2 in wait_text(page, "#my_state_user", U2))
    cap.check("whoami email (substate computed var)", f"{U2}@example.com" in wait_text(page, "#my_state_email", "@example.com"))
    page.click("#probe")
    t = wait_text(page, "#whoami_message", "user=")
    cap.check("whoami probe handler (get_state + inherited computed)", f"user={U2}" in t and "auth=True" in t and "same_token=True" in t and f"email={U2}@example.com" in t, t)
    # switch user without reload: logout + login as U1 and check the substate computed var updates
    page.click("#whoami_logout")
    cap.check("whoami after logout: email cleared", "no-info" in wait_text(page, "#my_state_email", "no-info"))
    page.goto(BASE + "/login", wait_until="networkidle")
    page.wait_for_selector("input#username")
    fill_form(page, {"username": U1, "password": PW}, "Sign in")
    page.wait_for_timeout(1500)
    page.goto(BASE + "/tp-whoami", wait_until="networkidle")
    cap.check("whoami after user switch shows U1", U1 in wait_text(page, "#my_state_user", U1))
    cap.check("whoami after user switch: no email for U1", "no-info" in wait_text(page, "#my_state_email", "no-info"))
    page.click("#probe")
    t = wait_text(page, "#whoami_message", f"user={U1}")
    cap.check("whoami probe after switch", f"user={U1}" in t and "email=None" in t, t)
    page.click("#whoami_logout")
    wait_text(page, "#my_state_user", r"^\s*$")

    cap.label = "strict-register"
    page.goto(BASE + "/tp-strict-register", wait_until="networkidle")
    page.wait_for_selector("input#username")
    fill_form(page, {"username": U3, "password": "abc", "confirm_password": "abc"}, "Strict sign up")
    page.wait_for_timeout(2500)
    err = page.locator("#strict_error").inner_text() if page.locator("#strict_error").count() else "<gone>"
    succ = page.locator("#strict_success").inner_text() if page.locator("#strict_success").count() else "<gone>"
    cap.check(
        "subclass override of _validate_fields honoured via self.handle_registration()",
        "STRICT" in err,
        f"error_message={err!r} success={succ!r} url={page.url}",
    )
    shot(page, "06-strict-register")
    if DB:
        import sqlite3

        con = sqlite3.connect(DB)
        row = con.execute("select id, username, enabled from localuser where username=?", (U3,)).fetchone()
        con.close()
        cap.check("short-password user NOT created by strict register (DB)", row is None, f"db row={row}")

    cap.label = "expiry"
    page.goto(BASE + "/register", wait_until="networkidle")
    page.wait_for_selector("input#username")
    fill_form(page, {"username": U4, "password": PW, "confirm_password": PW}, "Sign up")
    wait_text(page, "body", "Registration successful")
    wait_url(page, r"/login", 10)
    page.goto(BASE + "/tp-expiry", wait_until="networkidle")
    page.wait_for_selector("input#username")
    fill_form(page, {"username": U4, "password": PW}, "Quick login")
    cap.check("short session login", f"short session for {U4}" in wait_text(page, "#short_message", "short session"))
    cap.check("short session authenticated", "authenticated=yes" in wait_text(page, "#expiry_auth", "yes"))
    p3 = cap.attach(ctx.new_page(), "tab3")
    p3.goto(BASE + "/need2login", wait_until="networkidle")
    cap.check("new tab while session valid -> protected content", "Accessing this page" in wait_text(p3, "body", "Accessing this page"))
    p3.close()
    page.wait_for_timeout(7500)
    p4 = cap.attach(ctx.new_page(), "tab4")
    p4.goto(BASE + "/need2login", wait_until="networkidle")
    cap.check("new tab after session expiry -> /login", "/login" in wait_url(p4, r"/login"), p4.url)
    shot(p4, "07-expired")
    p4.close()

    cap.label = "end"
    shot(page, "08-end")
    ctx.close()

cap.dump(OUT / f"{LABEL}-report.json", {"users": [U1, U2, U3, U4]})
