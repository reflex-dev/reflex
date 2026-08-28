"""Playwright driver for form-designer example app (reflex[db] + reflex-local-auth).

Usage:
  python drive_form_designer.py <label> <url> full <username> <formname>
      register user, login, create form, add text+radio fields, preview,
      submit entry, check responses, logout, re-login, verify persistence
  python drive_form_designer.py <label> <url> relogin <username> <formname>
      login existing user, verify form + fields persist, submit another
      entry, check responses

Password is fixed. Artifacts land in ./artifacts/<label>_fd_*.
"""

import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

LABEL, URL, MODE, USERNAME, FORMNAME = sys.argv[1:6]
PASSWORD = "S3cretPass!42"
ART = Path(__file__).parent / "artifacts"
ART.mkdir(exist_ok=True)

console_msgs = []
failed_requests = []
results = []


def check(name, ok, detail=""):
    results.append({"name": name, "ok": bool(ok), "detail": str(detail)[:500]})
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}")


def shot(page, name):
    page.screenshot(path=str(ART / f"{LABEL}_fd_{name}.png"))


def login(page, base):
    """Sign in; returns True if the app auto-redirected away from /login.

    NOTE: on the 0.9.8 baseline LoginState.redir() does NOT fire a redirect
    after sign-in (user stays on /login but IS authenticated), so callers
    verify auth by loading a protected page instead.
    """
    page.goto(base.rstrip("/") + "/login", wait_until="load")
    page.locator('input[name="username"]').wait_for(timeout=20000)
    page.fill('input[name="username"]', USERNAME)
    page.fill('input[name="password"]', PASSWORD)
    page.get_by_role("button", name="Sign in").click()
    time.sleep(3.0)
    return "/login" not in page.url


def assert_authenticated(page, base):
    """Protected editor page renders Form Name input (no bounce to /login)."""
    page.goto(base.rstrip("/") + "/edit/form/", wait_until="load")
    page.locator('input[placeholder="Form Name"]').wait_for(timeout=20000)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = browser.new_context(viewport={"width": 1280, "height": 1000})
    page = ctx.new_page()
    page.on("console", lambda m: console_msgs.append({"type": m.type, "text": m.text}))
    page.on(
        "requestfailed",
        lambda r: failed_requests.append({"url": r.url, "failure": str(r.failure)}),
    )
    page.on(
        "response",
        lambda r: failed_requests.append({"url": r.url, "status": r.status})
        if r.status >= 400
        else None,
    )
    base = URL.rstrip("/")

    # home page
    page.goto(base + "/", wait_until="load")
    try:
        page.get_by_role("link", name="Create or Edit Forms").wait_for(timeout=30000)
        check("home page loads with Create/Edit link", True)
    except Exception as e:
        check("home page loads with Create/Edit link", False, e)
    shot(page, "home")

    if MODE == "full":
        # register
        page.goto(base + "/register/", wait_until="load")
        page.locator('input[name="username"]').wait_for(timeout=20000)
        page.fill('input[name="username"]', USERNAME)
        page.fill('input[name="password"]', PASSWORD)
        page.fill('input[name="confirm_password"]', PASSWORD)
        shot(page, "register_filled")
        page.get_by_role("button", name="Sign up").click()
        try:
            page.wait_for_url(re.compile(r".*/login.*"), timeout=20000)
            check("registration succeeds and redirects to /login", True)
        except Exception as e:
            check("registration succeeds and redirects to /login", False, e)
            shot(page, "register_fail")

        # login
        try:
            redirected = login(page, base)
            check("login auto-redirects away from /login", redirected, page.url)
        except Exception as e:
            check("login auto-redirects away from /login", False, e)
            shot(page, "login_fail")

        # create a form
        try:
            assert_authenticated(page, base)
            check("login authenticates (protected editor page renders)", True)
        except Exception as e:
            check("login authenticates (protected editor page renders)", False, e)
        page.fill('input[placeholder="Form Name"]', FORMNAME)
        try:
            page.wait_for_url(re.compile(r".*/edit/form/\d+.*"), timeout=20000)
            form_id = re.search(r"/edit/form/(\d+)", page.url).group(1)
            check("typing form name creates form and redirects to /edit/form/<id>", True, page.url)
        except Exception as e:
            form_id = None
            check("typing form name creates form and redirects to /edit/form/<id>", False, e)
        shot(page, "form_created")

        # add a text field
        try:
            page.get_by_role("button", name="Add Field").click()
            dlg = page.get_by_role("dialog").filter(has_text="Edit Field")
            dlg.locator('input[name="field_name"]').wait_for(timeout=15000)
            dlg.locator('input[name="field_name"]').fill("favorite_food")
            dlg.locator('input[name="field_prompt"]').fill("What is your favorite food?")
            shot(page, "field_text_modal")
            dlg.get_by_role("button", name="Save").click()
            page.wait_for_url(re.compile(r".*/edit/form/\d+/?$"), timeout=15000)
            page.get_by_text("What is your favorite food?").first.wait_for(timeout=10000)
            check("text field added and listed on form editor", True)
        except Exception as e:
            check("text field added and listed on form editor", False, e)
            shot(page, "field_text_fail")

        # add a radio field with options
        try:
            page.get_by_role("button", name="Add Field").click()
            dlg = page.get_by_role("dialog").filter(has_text="Edit Field")
            dlg.locator('input[name="field_name"]').wait_for(timeout=15000)
            dlg.locator('input[name="field_name"]').fill("color")
            dlg.locator('input[name="field_prompt"]').fill("Favorite color")
            dlg.get_by_role("combobox").click()
            page.get_by_role("option", name="radio").click()
            dlg.get_by_role("button", name="Edit Options").wait_for(timeout=10000)
            dlg.get_by_role("button", name="Edit Options").click()
            odlg = page.get_by_role("dialog").filter(has_text="Edit Options")
            odlg.wait_for(timeout=10000)
            plus = odlg.get_by_role("button").filter(has=page.locator("svg.lucide-plus"))
            plus.click()
            odlg.locator(".fd-Option-Label input").last.wait_for(timeout=10000)
            odlg.locator(".fd-Option-Label input").last.fill("Red")
            time.sleep(0.7)
            plus.click()
            time.sleep(0.7)
            odlg.locator(".fd-Option-Label input").last.fill("Blue")
            time.sleep(0.7)
            shot(page, "options_editor")
            odlg.get_by_role("button", name="Done").click()
            dlg.get_by_role("button", name="Save").click()
            page.wait_for_url(re.compile(r".*/edit/form/\d+/?$"), timeout=15000)
            page.get_by_text("Favorite color").first.wait_for(timeout=10000)
            check("radio field with 2 options added", True)
        except Exception as e:
            check("radio field with 2 options added", False, e)
            shot(page, "field_radio_fail")
        shot(page, "form_with_fields")

    else:
        # relogin mode: login as existing user
        try:
            redirected = login(page, base)
            assert_authenticated(page, base)
            check("relogin as existing user succeeds", True, f"auto-redirect={redirected}")
        except Exception as e:
            check("relogin as existing user succeeds", False, e)
            shot(page, "login_fail")
        # find the form by id 1 (first created form)
        page.goto(base + "/edit/form/1", wait_until="load")
        try:
            page.locator('input[placeholder="Form Name"]').wait_for(timeout=20000)
            page.wait_for_function(
                "document.querySelector('input[placeholder=\"Form Name\"]').value !== ''",
                timeout=15000,
            )
            val = page.locator('input[placeholder="Form Name"]').input_value()
            check("existing form persists after upgrade/restart", val == FORMNAME, f"name={val!r}")
            page.get_by_text("What is your favorite food?").first.wait_for(timeout=10000)
            page.get_by_text("Favorite color").first.wait_for(timeout=5000)
            check("existing fields persist (text + radio)", True)
        except Exception as e:
            check("existing form persists after upgrade/restart", False, e)
            check("existing fields persist (text + radio)", False, "see above")
        form_id = "1"
        shot(page, "form_persisted")

    # preview + submit an entry (both modes)
    entry_submitted = False
    entry_value = f"pizza-{LABEL}"
    if form_id:
        # NOTE: on the 0.9.8 baseline this page crashes into the error boundary
        # with "FormMessage must be used within FormField or specify the name
        # prop" (app-level incompatibility with current radix form) — record
        # actual behavior for cross-version comparison.
        page.goto(base + f"/form/{form_id}", wait_until="load")
        time.sleep(2.0)
        body = page.inner_text("body")
        crashed = "An error occurred while rendering this page" in body
        check(
            "form entry (preview) page renders without error boundary",
            not crashed,
            "error boundary shown" if crashed else "",
        )
        shot(page, "entry_page")
        if not crashed:
            try:
                page.get_by_role("heading", name=FORMNAME).wait_for(timeout=10000)
                page.locator('input[name="favorite_food"]').fill(entry_value)
                page.get_by_text("Red", exact=True).click()
                shot(page, "entry_filled")
                page.get_by_role("button", name="Submit").click()
                page.wait_for_url(re.compile(r".*/form/success.*"), timeout=15000)
                page.get_by_text("Your response has been saved!").wait_for(timeout=10000)
                check("form entry submits and shows success page", True)
                entry_submitted = True
            except Exception as e:
                check("form entry submits and shows success page", False, e)
                shot(page, "entry_fail")
        else:
            check("form entry submits and shows success page", False, "entry page crashed")

        # responses page
        try:
            page.goto(base + f"/responses/{form_id}", wait_until="load")
            time.sleep(2.0)
            body = page.inner_text("body")
            check(
                "responses page renders without error boundary",
                "An error occurred while rendering this page" not in body,
            )
            if entry_submitted:
                btns = page.locator("h3 > button[data-state='closed']")
                for i in range(btns.count()):
                    btns.nth(i).click()
                    time.sleep(0.3)
                body = page.inner_text("body")
                check(
                    "responses page shows submitted entry",
                    entry_value in body and "Red" in body,
                    f"looked for {entry_value!r} and 'Red'",
                )
        except Exception as e:
            check("responses page renders without error boundary", False, e)
        shot(page, "responses")

    if MODE == "full":
        # logout via navbar menu
        try:
            page.goto(base + "/", wait_until="load")
            page.locator("svg.lucide-menu").wait_for(timeout=15000)
            page.locator("svg.lucide-menu").click()
            page.get_by_role("menuitem", name="Logout").click()
            time.sleep(1.0)
            # after logout, /edit/form/ should bounce to /login
            page.goto(base + "/edit/form/", wait_until="load")
            page.wait_for_url(re.compile(r".*/login.*"), timeout=20000)
            check("logout works; protected page redirects to /login", True)
        except Exception as e:
            check("logout works; protected page redirects to /login", False, e)
            shot(page, "logout_fail")

        # re-login and verify form persists
        try:
            login(page, base)
            assert_authenticated(page, base)
            page.goto(base + f"/edit/form/{form_id}", wait_until="load")
            page.locator('input[placeholder="Form Name"]').wait_for(timeout=20000)
            page.wait_for_function(
                "document.querySelector('input[placeholder=\"Form Name\"]').value !== ''",
                timeout=15000,
            )
            val = page.locator('input[placeholder="Form Name"]').input_value()
            check("re-login shows persisted form", val == FORMNAME, f"name={val!r}")
        except Exception as e:
            check("re-login shows persisted form", False, e)
        shot(page, "final")

    time.sleep(1)
    browser.close()

(ART / f"{LABEL}_fd_console.json").write_text(json.dumps(console_msgs, indent=2))
(ART / f"{LABEL}_fd_netfail.json").write_text(json.dumps(failed_requests, indent=2))
(ART / f"{LABEL}_fd_results.json").write_text(json.dumps(results, indent=2))

unexpected = [
    m
    for m in console_msgs
    if m["type"] in ("error", "warning")
    and "HydrateFallback" not in m["text"]
    and "React DevTools" not in m["text"]
    and "[vite] connecting" not in m["text"]
    and "[vite] connected" not in m["text"]
]
print(f"\nconsole: {len(console_msgs)} msgs, {len(unexpected)} unexpected err/warn")
for m in unexpected:
    print("  UNEXPECTED:", m["type"], m["text"][:300])
print(f"failed/4xx+ requests: {failed_requests}")
print("ALL_OK" if all(r["ok"] for r in results) else "SOME_FAILED")
