"""Drive the reflex-examples form-designer app (reflex[db] + reflex-local-auth).

Usage:
  drive_form_designer.py <url> <outdir> <tag> <mode> <profile_dir> [expect_version]

modes:
  full   fresh DB: home, register, login, create form, add text/number/radio/select
         fields (options dialog + rx.call_script focus), preview page, logout,
         protected-page bounce, re-login (left logged in, persistent profile).
  up     existing DB + SAME browser profile: home/version, protected editor WITHOUT
         logging in (LocalStorage auth token hydration), form list, persisted form +
         fields, add an email field, logout/login round trip (left logged in).
  entry  (needs FD_FIX_FIELD_NAME=1 on the server) preview page: required-field
         toast, fill + submit, success page, responses page (rx.moment, rx.Cookie
         client token, accordion), lists every response text found.
A persistent Chromium profile carries LocalStorage/cookies across runs/versions.
"""

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from harness import CHROMIUM, Run, guard_driver_python, wait_for  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

guard_driver_python()
URL, OUT, TAG, MODE, PROFILE = sys.argv[1:6]
EXPECT_VERSION = sys.argv[6] if len(sys.argv) > 6 else None
BASE = URL.rstrip("/")
USER, PASSWORD, FORMNAME = "qa_admin", "S3cretPass!42", "Upgrade Survey"
run = Run(TAG, OUT)
run.notes.update({"mode": MODE, "url": URL})


def body(page):
    try:
        return page.inner_text("body")
    except Exception:  # noqa: BLE001
        return ""


def crashed(page):
    return "An error occurred while rendering this page" in body(page)


def form_name_input(page):
    return page.locator('input[placeholder="Form Name"]')


def editor_ready(page, timeout=25000):
    form_name_input(page).wait_for(timeout=timeout)


def login(page):
    page.goto(BASE + "/login", wait_until="load")
    page.locator('input[name="username"]').wait_for(timeout=25000)
    page.fill('input[name="username"]', USER)
    page.fill('input[name="password"]', PASSWORD)
    page.get_by_role("button", name="Sign in").click()
    time.sleep(3.0)
    return page.url


def logout(page):
    page.goto(BASE + "/", wait_until="load")
    page.get_by_role("link", name="Create or Edit Forms").wait_for(timeout=25000)
    page.locator("svg.lucide-menu").click()
    page.get_by_role("menuitem", name="Logout").click()
    time.sleep(1.5)


def add_field(page, name, prompt, type_=None, options=(), required=False, label=""):
    page.get_by_role("button", name="Add Field").click()
    dlg = page.get_by_role("dialog").filter(has_text="Edit Field")
    dlg.locator('input[name="field_name"]').wait_for(timeout=15000)
    dlg.locator('input[name="field_name"]').fill(name)
    dlg.locator('input[name="field_prompt"]').fill(prompt)
    focus_ok = None
    if type_:
        dlg.get_by_role("combobox").click()
        page.get_by_role("option", name=type_, exact=True).click()
        time.sleep(0.5)
    if options:
        dlg.get_by_role("button", name="Edit Options").click()
        odlg = page.get_by_role("dialog").filter(has_text="Edit Options")
        odlg.wait_for(timeout=10000)
        plus = odlg.get_by_role("button").filter(has=page.locator("svg.lucide-plus"))
        focus_ok = True
        for i, opt in enumerate(options):
            plus.click()
            wait_for(lambda: odlg.locator(".fd-Option-Label input").count() == i + 1, 8)
            # rx.call_script focuses the newest option input after 100ms
            focused = wait_for(lambda: page.evaluate(
                "() => { const a = Array.from(document.querySelectorAll('.fd-Option-Label input'));"
                " return a.length > 0 && document.activeElement === a[a.length-1]; }"), 4)
            focus_ok = focus_ok and bool(focused)
            odlg.locator(".fd-Option-Label input").last.fill(opt)
            time.sleep(0.8)
        run.shot(page, f"options_{name}")
        odlg.get_by_role("button", name="Done").click()
        time.sleep(0.5)
    if required:
        dlg.get_by_role("checkbox", name="Required").click()
        time.sleep(0.3)
    run.shot(page, f"field_modal_{name}")
    dlg.get_by_role("button", name="Save").click()
    page.wait_for_url(re.compile(r".*/edit/form/\d+/?$"), timeout=15000)
    page.get_by_text(prompt).first.wait_for(timeout=10000)
    return focus_ok


def fields_listed(page):
    return [t for t in page.locator(".rt-Card a").all_inner_texts() if t.strip()]


with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(PROFILE, executable_path=CHROMIUM,
                                               viewport={"width": 1280, "height": 1000})
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    run.attach(page)

    page.goto(BASE + "/", wait_until="load")
    try:
        page.get_by_role("link", name="Create or Edit Forms").wait_for(timeout=40000)
        txt = body(page)
        ver = re.search(r"\bv(\d+\.\d+\.\d+\S*)", txt)
        run.check("home: renders link + README markdown", "This is the Form Designer sample app" in txt,
                  f"version shown={ver.group(1) if ver else None}")
        if EXPECT_VERSION:
            run.check("home: importlib version text matches installed reflex",
                      bool(ver) and ver.group(1) == EXPECT_VERSION, f"{ver.group(1) if ver else None} vs {EXPECT_VERSION}")
        run.notes["md_h1"] = page.locator("h1").all_inner_texts()
    except Exception as e:  # noqa: BLE001
        run.check("home: renders link + README markdown", False, e)
    run.shot(page, "home")

    form_id = None
    if MODE == "full":
        page.goto(BASE + "/register", wait_until="load")
        page.locator('input[name="username"]').wait_for(timeout=25000)
        page.fill('input[name="username"]', USER)
        page.fill('input[name="password"]', PASSWORD)
        page.fill('input[name="confirm_password"]', PASSWORD)
        page.get_by_role("button", name="Sign up").click()
        try:
            page.get_by_text("Registration successful!").wait_for(timeout=10000)
            page.wait_for_url(re.compile(r".*/login.*"), timeout=15000)
            run.check("register: success message then redirect to /login", True, page.url)
        except Exception as e:  # noqa: BLE001
            run.check("register: success message then redirect to /login", False, e)
            run.shot(page, "register_fail")
        url_after = login(page)
        run.check("login: auto-redirects away from /login (pre-existing FAIL on 0.9.x)",
                  "pass" if "/login" not in url_after else "anomaly", url_after)
        ls = page.evaluate("() => window.localStorage.getItem('_auth_token')")
        run.check("login: LocalStorage _auth_token written", bool(ls), f"len={len(ls or '')}")
        run.notes["auth_token_after_login"] = ls
        page.goto(BASE + "/edit/form/", wait_until="load")
        try:
            editor_ready(page)
            run.check("login: protected /edit/form/ renders", True)
        except Exception as e:  # noqa: BLE001
            run.check("login: protected /edit/form/ renders", False, e)
        form_name_input(page).fill(FORMNAME)
        try:
            page.wait_for_url(re.compile(r".*/edit/form/\d+.*"), timeout=20000)
            form_id = re.search(r"/edit/form/(\d+)", page.url).group(1)
            run.check("create form: debounced name input creates form + redirect", True, page.url)
        except Exception as e:  # noqa: BLE001
            run.check("create form: debounced name input creates form + redirect", False, e)
        run.shot(page, "form_created")
        specs = [
            ("favorite_food", "What is your favorite food?", None, (), False),
            ("age", "How old are you?", "number", (), True),
            ("color", "Favorite color", "radio", ("Red", "Blue"), False),
            ("size", "Shirt size", "select", ("Small", "Large"), False),
        ]
        for name, prompt, type_, opts, req in specs:
            try:
                focus = add_field(page, name, prompt, type_, opts, req)
                run.check(f"add field {name} ({type_ or 'text'}{', required' if req else ''})", True,
                          f"options={list(opts)}")
                if opts:
                    run.check(f"add field {name}: rx.call_script focused newest option input", bool(focus))
            except Exception as e:  # noqa: BLE001
                run.check(f"add field {name} ({type_ or 'text'})", False, e)
                run.shot(page, f"field_{name}_fail")
                page.keyboard.press("Escape")
                if form_id:
                    page.goto(BASE + f"/edit/form/{form_id}", wait_until="load")
        page.reload(wait_until="load")
        editor_ready(page)
        time.sleep(2)
        run.notes["fields_after_add"] = fields_listed(page)
        run.check("editor lists 4 fields after reload", len(run.notes["fields_after_add"]) == 4,
                  run.notes["fields_after_add"])
        run.shot(page, "form_with_fields")
    elif MODE in ("up", "entry"):
        page.goto(BASE + "/edit/form/", wait_until="load")
        try:
            editor_ready(page, 30000)
            run.check("auth survives (LocalStorage token): /edit/form/ renders WITHOUT login", True)
        except Exception as e:  # noqa: BLE001
            run.check("auth survives (LocalStorage token): /edit/form/ renders WITHOUT login", False,
                      f"{e!s:.200} url={page.url}")
            run.shot(page, "auth_lost")
            login(page)
            page.goto(BASE + "/edit/form/", wait_until="load")
            editor_ready(page, 30000)
        run.notes["auth_token"] = page.evaluate("() => window.localStorage.getItem('_auth_token')")
        page.get_by_role("combobox").first.click()
        try:
            opt = page.get_by_role("option", name=FORMNAME)
            opt.wait_for(timeout=10000)
            run.check("existing form listed in 'Existing Forms' select (on_mount load)", True)
            opt.click()
            page.wait_for_url(re.compile(r".*/edit/form/\d+.*"), timeout=15000)
            form_id = re.search(r"/edit/form/(\d+)", page.url).group(1)
        except Exception as e:  # noqa: BLE001
            run.check("existing form listed in 'Existing Forms' select (on_mount load)", False, e)
            page.keyboard.press("Escape")
            form_id = "1"
            page.goto(BASE + "/edit/form/1", wait_until="load")
        editor_ready(page)
        wait_for(lambda: form_name_input(page).input_value() != "", 15)
        run.check("persisted form name", form_name_input(page).input_value() == FORMNAME,
                  form_name_input(page).input_value())
        time.sleep(1.5)
        fl = fields_listed(page)
        run.notes["fields_listed"] = fl
        run.check("persisted fields listed", len(fl) >= 4, fl)
        run.shot(page, "form_persisted")
        if MODE == "up":
            try:
                add_field(page, f"email_{TAG}", f"Your email ({TAG})", "email")
                run.check("add another field (email) after upgrade", True)
            except Exception as e:  # noqa: BLE001
                run.check("add another field (email) after upgrade", False, e)
                run.shot(page, "add_email_fail")

    if form_id:
        run.notes["form_id"] = form_id
        page.goto(BASE + f"/form/{form_id}", wait_until="load")
        time.sleep(3)
        c = crashed(page)
        run.shot(page, "entry_page")
        if MODE != "entry":
            run.check("entry page /form/<id>: renders (pre-existing FormMessage crash unless FD_FIX)",
                      "pass" if not c else "anomaly",
                      "error boundary: " + next((m["text"][:200] for m in run.console if "FormMessage" in m["text"]), "?") if c else "rendered")
        else:
            run.check("entry page renders (FD_FIX_FIELD_NAME=1)", not c)
            if not c:
                entry_val = f"pizza-{TAG}"
                page.locator('input[name="favorite_food"]').fill(entry_val)
                page.get_by_role("button", name="Submit").click()
                # radix Form native validation blocks submit for the required number field,
                # so the server-side toast path may not trigger; record both outcomes.
                toast = wait_for(lambda: page.locator("[data-sonner-toast]").count() > 0, 4)
                msg = page.locator("[data-sonner-toast]").first.inner_text() if toast else ""
                run.notes["required_submit_toast"] = msg
                stayed = "/form/success" not in page.url
                run.check("required field missing: submit blocked (toast or native validation)", stayed,
                          f"toast={msg!r} url={page.url}")
                run.shot(page, "entry_required")
                page.locator('input[name="age"]').fill("42")
                page.get_by_text("Blue", exact=True).click()
                page.get_by_role("combobox").first.click()
                page.get_by_role("option", name="Large").click()
                run.shot(page, "entry_filled")
                page.get_by_role("button", name="Submit").click()
                try:
                    page.wait_for_url(re.compile(r".*/form/success.*"), timeout=15000)
                    page.get_by_text("Your response has been saved!").wait_for(timeout=10000)
                    run.check("entry submits -> /form/success", True)
                except Exception as e:  # noqa: BLE001
                    run.check("entry submits -> /form/success", False, e)
                    run.shot(page, "entry_submit_fail")
                ck = [c for c in ctx.cookies() if "client_token" in c["name"]]
                run.notes["client_token_cookie"] = ck[0]["value"] if ck else None
                run.check("rx.Cookie client_token set in browser", bool(ck), ck[0]["value"] if ck else "")
            page.goto(BASE + f"/responses/{form_id}", wait_until="load")
            time.sleep(3)
            run.check("responses page renders", not crashed(page))
            triggers = page.locator("h3 > button[data-state='closed']")
            n = triggers.count()
            for _ in range(n):
                if triggers.count() == 0:
                    break
                triggers.first.click()
                time.sleep(0.4)
            time.sleep(1.0)
            txt = body(page)
            run.notes["responses_text"] = txt[-3000:]
            vals = sorted(set(re.findall(r"pizza-[\w.-]+", txt)))
            run.notes["responses_values"] = vals
            run.check("responses page lists submitted entries", f"pizza-{TAG}" in vals, f"{n} responses: {vals}")
            stamps = page.evaluate("() => Array.from(document.querySelectorAll('time')).map(t => [t.dateTime || t.getAttribute('datetime'), t.textContent])")
            run.notes["moment_times"] = stamps
            run.check("rx.moment renders response timestamps", len(stamps) >= 1 and all(s[1] for s in stamps), stamps)
            run.shot(page, "responses")

    if MODE in ("full", "up"):
        try:
            logout(page)
            page.goto(BASE + "/edit/form/", wait_until="load")
            page.wait_for_url(re.compile(r".*/login.*"), timeout=25000)
            run.check("logout: protected page bounces to /login", True, page.url)
        except Exception as e:  # noqa: BLE001
            run.check("logout: protected page bounces to /login", False, f"{e!s:.200} url={page.url}")
            run.shot(page, "logout_fail")
        try:
            u = login(page)
            run.check("re-login: auto-redirects away from /login (pre-existing FAIL on 0.9.x)",
                      "pass" if "/login" not in u else "anomaly", u)
            page.goto(BASE + "/edit/form/", wait_until="load")
            editor_ready(page)
            run.check("re-login works (left logged in for next run)", True)
        except Exception as e:  # noqa: BLE001
            run.check("re-login works (left logged in for next run)", False, e)
        run.shot(page, "final")
    run.notes["final_local_storage"] = page.evaluate("() => Object.assign({}, window.localStorage)")
    run.notes["final_cookies"] = ctx.cookies()
    ctx.close()

sys.exit(run.finish())
