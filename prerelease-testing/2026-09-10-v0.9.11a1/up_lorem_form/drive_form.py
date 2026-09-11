"""Drive the reflex-examples `form-designer` app (reflex[db] + reflex-local-auth) end to end.

usage: drive_form.py <frontend_url> <artifacts_dir> <label> [<app_dir>]

Flow: register (with the password-mismatch and duplicate-username errors), login
(wrong then right password), create a form, add/rename/require a text field, add a
select field with an option, preview, hit the required-field validation, submit a
response while logged in, log out and submit anonymously, check that /responses is
login-gated, view both responses, delete one, delete a field, delete the form.
"""

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from drive_common import Run, wait_for  # noqa: E402


def main():
    base = sys.argv[1].rstrip("/") + "/"
    art = sys.argv[2]
    label = sys.argv[3]
    app_dir = sys.argv[4] if len(sys.argv) > 4 else None

    suffix = str(int(time.time()) % 1000000)
    user = f"u{suffix}"
    password = "foobarbaz43"
    form_name = f"F-{suffix}"

    with Run(art, label) as run:
        (Path(art) / "identifiers.json").write_text(
            json.dumps({"user": user, "form_name": form_name})
        )
        ctx, page = run.new_page()
        page.set_default_timeout(20000)

        def cur_url():
            return page.evaluate("() => location.href")

        def at_home(timeout=20000):
            return wait_for(lambda: cur_url().rstrip("/") == base.rstrip("/"), timeout / 1000)

        def url_is(pattern, timeout=20000):
            try:
                page.wait_for_url(re.compile(base + pattern), timeout=timeout)
                return True
            except Exception:  # noqa: BLE001
                return False

        # --- 1. home page renders (markdown README card + reflex version) -------
        page.goto(base, wait_until="networkidle")
        page.wait_for_timeout(1200)
        run.shot(page, "01_home.png")
        has_readme = page.get_by_text("Create a Form", exact=False).count() > 0
        version_txt = ""
        try:
            version_txt = page.locator("p.rt-Text", has_text=re.compile(r"^v0\.9\.")).first.inner_text()
        except Exception:  # noqa: BLE001
            pass
        run.record(
            "home_page_renders",
            "pass" if has_readme and page.get_by_role("link", name="Create or Edit Forms").is_visible() else "fail",
            f"readme_markdown_rendered={has_readme} edit_link=True version_badge={version_txt}",
        )

        # --- 2. login gate on the editor -----------------------------------------
        page.get_by_role("link", name="Create or Edit Forms").click()
        run.record(
            "editor_redirects_to_login",
            "pass" if url_is("login/?") else "fail",
            f"url={cur_url()}",
        )

        # --- 3. register: password mismatch, then success -------------------------
        page.goto(base + "register", wait_until="networkidle")
        page.locator("id=username").fill(user)
        page.locator("id=password").fill(password)
        page.get_by_role("button", name="Sign up").click()
        mismatch = wait_for(lambda: page.get_by_text("Passwords do not match").is_visible(), 10)
        run.record(
            "register_password_mismatch_error",
            "pass" if mismatch else "fail",
            f"error_shown={mismatch}",
        )
        page.locator("id=confirm_password").fill(password)
        page.get_by_role("button", name="Sign up").click()
        registered = url_is("login/?")
        run.record(
            "register_new_user",
            "pass" if registered else "fail",
            f"redirected_to_login={registered}",
        )
        run.shot(page, "02_registered.png")

        # --- 4. duplicate registration is rejected --------------------------------
        page.goto(base + "register", wait_until="networkidle")
        page.locator("id=username").fill(user)
        page.locator("id=password").fill(password)
        page.locator("id=confirm_password").fill(password)
        page.get_by_role("button", name="Sign up").click()
        dup = wait_for(
            lambda: page.get_by_text(re.compile("is already registered")).is_visible(), 10
        )
        run.record(
            "duplicate_username_rejected",
            "pass" if dup else "fail",
            f"error_shown={dup}",
        )

        # --- 5. login: wrong password then correct --------------------------------
        page.goto(base + "login", wait_until="networkidle")
        page.locator("id=username").fill(user)
        page.locator("id=password").fill("wrong-password")
        page.get_by_role("button", name="Sign in").click()
        bad = wait_for(
            lambda: page.get_by_text("There was a problem logging in, please try again.").is_visible(), 10
        )
        run.record("login_wrong_password_error", "pass" if bad else "fail", f"error_shown={bad}")
        page.locator("id=password").fill(password)
        page.get_by_role("button", name="Sign in").click()
        t_login = time.time()
        left_login = wait_for(lambda: "/login" not in cur_url(), 30)
        landed = cur_url()[len(base) - 1 :] or "/"
        run.record(
            "login_success",
            "pass" if left_login and landed in ("/", "/edit/form/") else "fail",
            f"left_login_page={left_login} landed_on={landed} seconds={time.time() - t_login:.1f}",
        )
        if not left_login:
            # prod serves /login as a 307 to /login/, which defeats
            # reflex_local_auth's post-login redirect (router.url.path != LOGIN_ROUTE).
            # The session IS valid, so navigate manually and keep testing the app.
            page.goto(base + "edit/form/", wait_until="networkidle")
            page.wait_for_timeout(1000)
            run.record(
                "login_redirect_workaround_used",
                "anomaly",
                "post-login redirect never fired; navigated to /edit/form/ by hand",
            )
        else:
            run.record("login_redirect_workaround_used", "skipped", "post-login redirect worked")
        run.shot(page, "03_logged_in.png")

        # --- 6. the navbar menu shows the authenticated user ----------------------
        page.locator(".lucide-menu").click()
        shows_user = wait_for(lambda: page.get_by_text(user, exact=True).is_visible(), 8)
        run.record("menu_shows_username", "pass" if shows_user else "fail", f"username_visible={shows_user}")
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)

        # --- 7. create a form ------------------------------------------------------
        page.goto(base + "edit/form/", wait_until="networkidle")
        page.wait_for_timeout(800)
        page.locator("input[name='name']").fill(form_name)
        created = url_is(r"edit/form/\d+/?")
        form_id = cur_url().rstrip("/").rpartition("/")[2] if created else None
        run.record(
            "create_form",
            "pass" if created else "fail",
            f"redirected_to_form_route={created} has_numeric_id={bool(form_id and form_id.isdigit())}",
        )
        run.shot(page, "04_form_created.png")
        if not created:
            run.record("rest_of_flow", "fail", "aborted: form was never created")
            ctx.close()
            return

        # --- 8. add a text field ---------------------------------------------------
        page.get_by_role("button", name="Add Field").click()
        opened = url_is(r"edit/form/\d+/field/new/?")
        dialog = page.locator("div[role='dialog']")
        page.locator("input[name='field_name']").fill("Name")
        page.locator("input[name='field_prompt']").fill("Your name")
        dialog.get_by_role("button", name="Save").click()
        back = url_is(r"edit/form/\d+/?$")
        field_visible = wait_for(lambda: page.get_by_text("Your name (Name)").is_visible(), 10)
        run.record(
            "add_text_field",
            "pass" if opened and back and field_visible else "fail",
            f"modal_route={opened} returned_to_form={back} field_listed={field_visible}",
        )
        run.shot(page, "05_text_field.png")

        # --- 9. rename the field and mark it required ------------------------------
        page.get_by_text("Your name (Name)").click()
        url_is(r"edit/form/\d+/field/\d+/?")
        page.locator("input[name='field_name']").fill("FullName")
        page.locator("input[name='field_prompt']").fill("Your full name")
        dialog = page.locator("div[role='dialog']")
        dialog.get_by_role("checkbox").first.click()
        dialog.get_by_role("button", name="Save").click()
        url_is(r"edit/form/\d+/?$")
        renamed = wait_for(lambda: page.get_by_text("Your full name (FullName)").is_visible(), 10)
        required_marked = wait_for(lambda: page.get_by_text("(required)").is_visible(), 8)
        run.record(
            "edit_field_rename_and_require",
            "pass" if renamed and required_marked else "fail",
            f"renamed={renamed} shows_required={required_marked}",
        )
        run.shot(page, "06_field_required.png")

        # --- 10. add a select field with one option --------------------------------
        page.get_by_role("button", name="Add Field").click()
        url_is(r"edit/form/\d+/field/new/?")
        page.locator("input[name='field_name']").fill("Reflex")
        page.locator("input[name='field_prompt']").fill("Do you use Reflex")
        dialog = page.locator("div[role='dialog']")
        dialog.get_by_role("combobox").click()
        page.get_by_role("option", name="select", exact=True).click()
        page.wait_for_timeout(400)
        typed_select = wait_for(
            lambda: dialog.get_by_role("button", name="Edit Options").is_visible(), 8
        )
        dialog.get_by_role("button", name="Edit Options").click()
        page.wait_for_timeout(600)
        # the "+" icon button inside the options dialog adds an empty option row
        page.locator("button[type='submit']:has(svg)").last.click()
        got_option_row = wait_for(lambda: page.get_by_placeholder("Label").count() > 0, 10)
        page.get_by_placeholder("Label").first.fill("Assuredly")
        page.wait_for_timeout(600)
        page.get_by_placeholder("Assuredly").first.fill("Yes")
        page.wait_for_timeout(600)
        run.shot(page, "07_options.png")
        page.get_by_role("button", name="Done").click()
        page.wait_for_timeout(500)
        page.get_by_role("button", name="Save").last.click()
        url_is(r"edit/form/\d+/?$")
        select_listed = wait_for(
            lambda: page.get_by_text("Do you use Reflex (Reflex)").is_visible(), 10
        )
        run.record(
            "add_select_field_with_option",
            "pass" if typed_select and got_option_row and select_listed else "fail",
            f"type_select_applied={typed_select} option_row_added={got_option_row} field_listed={select_listed}",
        )
        run.shot(page, "08_two_fields.png")

        # --- 11. preview renders both fields ---------------------------------------
        page.get_by_role("button", name="Preview").click()
        previewing = url_is(r"form/\d+/?$")
        text_input = page.locator("input[name='FullName']")
        select_trigger = page.get_by_role("combobox").filter(has_text="Select an option")
        both = wait_for(lambda: text_input.is_visible() and select_trigger.is_visible(), 10)
        crashed = page.get_by_text("An error occurred while rendering this page").count() > 0
        run.record(
            "preview_renders_fields",
            "pass" if previewing and both and not crashed else "fail",
            f"url_is_form_route={previewing} text_input_and_select_visible={both} error_boundary_rendered={crashed}",
        )
        run.shot(page, "09_preview.png")
        form_url = cur_url()

        dependent = [
            "required_field_validation_toast",
            "submit_response_logged_in",
            "logout",
            "submit_response_anonymous",
            "responses_requires_login",
            "responses_page_lists_both",
            "response_values_visible",
            "delete_response",
        ]
        if crashed or not both:
            for name in dependent:
                run.record(name, "skipped", "form entry page did not render (see preview_renders_fields)")
            # still log out so the later editor steps run as the owner (they need auth, so
            # only log out at the very end in this branch): nothing to do here.
        else:

            # --- 12. required-field validation -----------------------------------------
            page.get_by_role("button", name="Submit").click()
            toasted = wait_for(
                lambda: page.get_by_text(re.compile("is missing a response")).count() > 0, 10
            )
            still_here = not re.search(r"form/success", cur_url())
            run.record(
                "required_field_validation_toast",
                "pass" if toasted and still_here else "fail",
                f"toast_shown={toasted} stayed_on_form={still_here}",
            )
            run.shot(page, "10_required_toast.png")

            # --- 13. submit a response while logged in ----------------------------------
            text_input.fill("Logged In")
            select_trigger.click()
            page.get_by_role("option", name="Assuredly").click()
            page.get_by_role("button", name="Submit").click()
            saved = url_is("form/success/?")
            run.record("submit_response_logged_in", "pass" if saved else "fail", f"url={cur_url()}")
            run.shot(page, "11_submitted.png")

            # --- 14. log out, then submit the same form anonymously ----------------------
            page.goto(base, wait_until="networkidle")
            page.locator(".lucide-menu").click()
            page.get_by_role("menuitem", name="Logout").click()
            logged_out = at_home()
            page.locator(".lucide-menu").click()
            anon = wait_for(lambda: page.get_by_text(user, exact=True).count() == 0, 8)
            page.keyboard.press("Escape")
            run.record(
                "logout",
                "pass" if logged_out and anon else "fail",
                f"redirected_home={logged_out} username_gone={anon}",
            )
            page.goto(form_url, wait_until="networkidle")
            page.wait_for_timeout(1000)
            anon_text = page.locator("input[name='FullName']")
            anon_select = page.get_by_role("combobox").filter(has_text="Select an option")
            anon_form_ok = wait_for(lambda: anon_text.is_visible() and anon_select.is_visible(), 10)
            anon_text.fill("Not logged in")
            anon_select.click()
            page.get_by_role("option", name="Assuredly").click()
            page.get_by_role("button", name="Submit").click()
            anon_saved = url_is("form/success/?")
            run.record(
                "submit_response_anonymous",
                "pass" if anon_form_ok and anon_saved else "fail",
                f"form_public={anon_form_ok} saved={anon_saved}",
            )
            run.shot(page, "12_anon_submitted.png")

            # --- 15. /responses is login-gated -----------------------------------------
            page.goto(base + f"responses/{form_id}/", wait_until="networkidle")
            gated = url_is("login/?")
            run.record("responses_requires_login", "pass" if gated else "fail", f"url={cur_url()}")

            # --- 16. log back in -> both responses visible ------------------------------
            page.locator("id=username").fill(user)
            page.locator("id=password").fill(password)
            page.get_by_role("button", name="Sign in").click()
            at_responses = url_is(r"responses/\d+/?")
            triggers = page.locator(".AccordionTrigger")
            two = wait_for(lambda: triggers.count() == 2, 15)
            run.record(
                "responses_page_lists_both",
                "pass" if at_responses and two else "fail",
                f"redirected_back_to_responses={at_responses} accordion_items={triggers.count()}",
            )
            run.shot(page, "13_responses.png")

            # --- 17. open a response and see the submitted values -----------------------
            if triggers.count():
                triggers.nth(1).click()
                page.wait_for_timeout(800)
                vals_visible = (
                    page.get_by_text("Not logged in").count() > 0
                    and page.get_by_text("Yes", exact=True).count() > 0
                )
                run.record(
                    "response_values_visible",
                    "pass" if vals_visible else "fail",
                    f"text_value_and_select_value_rendered={vals_visible}",
                )
                run.shot(page, "14_response_open.png", full_page=True)
            else:
                run.record("response_values_visible", "skipped", "no accordion items")

            # --- 18. delete one response ------------------------------------------------
            before = page.locator(".AccordionTrigger").count()
            page.locator(".AccordionTrigger .rt-Button").last.click()
            one_left = wait_for(lambda: page.locator(".AccordionTrigger").count() == before - 1, 12)
            run.record(
                "delete_response",
                "pass" if one_left else "fail",
                f"items_before={before} items_after={page.locator('.AccordionTrigger').count()}",
            )

        # --- 19. delete a field -----------------------------------------------------
        page.goto(base + f"edit/form/{form_id}/", wait_until="networkidle")
        page.wait_for_timeout(1200)
        fields_before = page.locator("div.rt-Card").count()
        page.get_by_role("link").filter(has=page.locator("svg.lucide-x")).last.click()
        field_gone = wait_for(
            lambda: page.get_by_text("Do you use Reflex (Reflex)").count() == 0, 12
        )
        run.record(
            "delete_field",
            "pass" if field_gone else "fail",
            f"select_field_removed={field_gone} cards_before={fields_before}",
        )
        run.shot(page, "15_field_deleted.png")

        # --- 20. delete the form ----------------------------------------------------
        page.get_by_role("button", name="Delete Form").click()
        deleted = url_is("edit/form/?$")
        page.wait_for_timeout(1200)
        page.get_by_role("combobox").first.click()
        page.wait_for_timeout(800)
        gone_from_list = page.get_by_role("option", name=re.compile(form_name)).count() == 0
        run.record(
            "delete_form",
            "pass" if deleted and gone_from_list else "fail",
            f"redirected_to_new_form={deleted} absent_from_dropdown={gone_from_list}",
        )
        page.keyboard.press("Escape")
        run.shot(page, "16_form_deleted.png")

        # --- 21. hygiene -------------------------------------------------------------
        unexpected = run.unexpected_console()
        run.record("no_unexpected_console", "pass" if not unexpected else "anomaly", json.dumps(unexpected)[:900])
        run.record("no_failed_or_4xx_requests", "pass" if not run.bad else "anomaly", json.dumps(run.bad)[:900])
        run.record("no_page_errors", "pass" if not run.page_errors else "fail", json.dumps(run.page_errors)[:900])

        if app_dir:
            pkg = Path(app_dir) / ".web" / "package.json"
            if pkg.exists():
                (Path(art) / "package.json").write_text(pkg.read_text())
            lock = Path(app_dir) / "reflex.lock" / "bun.lock"
            if lock.exists():
                (Path(art) / "bun.lock").write_text(lock.read_text())
        ctx.close()


main()
