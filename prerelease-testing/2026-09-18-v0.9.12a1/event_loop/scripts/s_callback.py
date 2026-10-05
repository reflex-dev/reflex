"""Scenario: #7156 / #7157 callback event routing. Usage: s_callback.py <base_url> <outdir>"""

import sys
import time
from pathlib import Path

sys.argv = [sys.argv[0], "callback", *sys.argv[1:]]
from playwright.sync_api import sync_playwright  # noqa: E402
from wsdrive import BASE, OUT, attach, dump, errors, log, txt  # noqa: E402

UPLOAD_FILE = OUT / "upload_me.txt"
UPLOAD_FILE.write_text("hello from the event_loop cluster\n")


def n_errors():
    return len(errors)


with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    page = ctx.new_page()
    attach(page, "c1")
    page.goto(f"{BASE}/callback", wait_until="networkidle")
    page.wait_for_selector("#cbevents", timeout=30000)
    time.sleep(1.0)

    def clear():
        page.click("#cbclear")
        page.wait_for_timeout(400)
        # dismiss any lingering toasts
        page.keyboard.press("Escape")

    def state():
        return txt(page, "#cbevents"), txt(page, "#cbuploaded")

    def click_toast(label, timeout=8000):
        page.wait_for_selector(f"[data-sonner-toast] >> text={label}", timeout=timeout)
        before = n_errors()
        page.click(f"[data-sonner-toast] >> text={label}")
        page.wait_for_timeout(900)
        new = errors[before:]
        return new

    # --- 1. frontend-fired toast, action -> State handler (#7157 core repro)
    clear()
    page.click("#fetoast")
    errs = click_toast("FE-Act")
    log("[1a fe-toast action] events=", state()[0], " pageerrors=", errs)
    page.click("#fetoast")
    errs = click_toast("FE-Cancel")
    log("[1b fe-toast cancel] events=", state()[0], " pageerrors=", errs)
    page.screenshot(path=str(OUT / "callback_fe_toast.png"))

    # --- 2. frontend-fired toast whose on_click is a pure client event spec
    clear()
    page.click("#fetoastjs")
    errs = click_toast("FE-Alert")
    alerted = page.evaluate("window.__alerted === true")
    log("[2 fe-toast js callback] window.__alerted=", alerted, " pageerrors=", errs)

    # --- 3. backend-yielded toast, action/cancel -> State handler
    clear()
    page.click("#betoast")
    errs = click_toast("BE-Act")
    log("[3a be-toast action] events=", state()[0], " pageerrors=", errs)
    page.click("#betoast")
    errs = click_toast("BE-Cancel")
    log("[3b be-toast cancel] events=", state()[0], " pageerrors=", errs)

    # --- 4. toast inside @rx.memo
    clear()
    page.click("#memotoast")
    errs = click_toast("Memo-Act")
    log("[4a memo toast action] events=", state()[0], " pageerrors=", errs)
    page.click("#memotoast")
    errs = click_toast("Memo-Cancel")
    log("[4b memo toast cancel] events=", state()[0], " pageerrors=", errs)

    # --- 5. toast inside rx.ComponentState
    clear()
    page.click("#cstoast")
    errs = click_toast("CS-Act")
    log("[5a component-state toast action] cshits=", txt(page, "#cshits"), " pageerrors=", errs)
    page.click("#cstoast")
    errs = click_toast("CS-Cancel")  # rx.set_clipboard
    log("[5b component-state toast cancel (set_clipboard)] pageerrors=", errs)

    # --- 6. call_script callback -> uploadFiles client handler (#7156)
    clear()
    page.set_input_files("#u2 input[type=file]", str(UPLOAD_FILE))
    page.wait_for_timeout(600)
    log("   (pre-check) events after dropping on u2 =", state()[0])
    page.click("#scriptupload")
    page.wait_for_timeout(2000)
    ran = page.evaluate("window.__cb_ran || 0")
    log("[6 call_script cb -> uploadFiles] __cb_ran=", ran, " events=", state()[0], " uploaded=", state()[1])
    page.screenshot(path=str(OUT / "callback_script_upload.png"))

    # --- 7. call_script callback -> State handler (eval path, must still work)
    clear()
    page.click("#scriptstate")
    page.wait_for_timeout(1200)
    log("[7 call_script cb -> state handler] events=", state()[0])

    # --- 8. frontend toast action -> uploadFiles
    clear()
    page.set_input_files("#u2 input[type=file]", str(UPLOAD_FILE))
    page.wait_for_timeout(600)
    page.click("#fetoastupload")
    errs = click_toast("FE-Upload")
    page.wait_for_timeout(1500)
    log("[8 fe-toast action -> uploadFiles] events=", state()[0], " uploaded=", state()[1], " pageerrors=", errs)

    # --- 9. backend toast action -> uploadFiles
    clear()
    page.set_input_files("#u2 input[type=file]", str(UPLOAD_FILE))
    page.wait_for_timeout(600)
    page.click("#betoastupload")
    errs = click_toast("BE-Upload")
    page.wait_for_timeout(1500)
    log("[9 be-toast action -> uploadFiles] events=", state()[0], " uploaded=", state()[1], " pageerrors=", errs)

    # --- 10. plain drop-zone upload still works
    clear()
    page.set_input_files("#u1 input[type=file]", str(UPLOAD_FILE))
    page.wait_for_timeout(2500)
    log("[10 direct on_drop upload] events=", state()[0], " uploaded=", state()[1])

    page.screenshot(path=str(OUT / "callback_final.png"))
    dump("callback")
    from wsdrive import console_log, net  # noqa: E402

    log("== console ==")
    for line in console_log:
        if any(
            s in line
            for s in ("Hey developer", "connecting", "connected", "React DevTools")
        ):
            continue
        log("  ", line)
    log("== pageerrors ==")
    for e in errors:
        log("  ", e)
    log("== net ==")
    for x in net:
        log("  ", x)
    ctx.close()
    b.close()
