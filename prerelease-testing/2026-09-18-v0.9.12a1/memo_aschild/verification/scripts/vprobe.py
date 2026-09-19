"""Independent verifier probe for cluster memo_aschild issues 1 and 3."""
import json
import sys
import time

from playwright.sync_api import sync_playwright

BASE = sys.argv[1]
OUT = sys.argv[2]


def txt(page, sel):
    try:
        return page.inner_text(sel, timeout=3000)
    except Exception as e:  # noqa
        return f"<ERR {type(e).__name__}>"


def main():
    log = []

    fh = open(f"{OUT}/vprobe.log", "w")

    def p(*a):
        line = " ".join(str(x) for x in a)
        print(line, flush=True)
        fh.write(line + "\n")
        fh.flush()
        log.append(line)

    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        ctx = b.new_context()
        page = ctx.new_page()
        errs = []
        page.on("console", lambda m: errs.append(f"CONSOLE[{m.type}] {m.text}") if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: errs.append(f"PAGEERROR {e}"))

        # ---------- triggers ----------
        page.goto(f"{BASE}/triggers", wait_until="networkidle")
        page.wait_for_timeout(1500)

        def clicks():
            return txt(page, "#out_clicks")

        def logv():
            return txt(page, "#out_log")

        p("TRIGGERS initial clicks=", clicks(), "log=", logv())

        # real mouse click on each trigger
        for name, sel, closer in [
            ("dialog", "#t_dialog", "#dialog_close"),
            ("popover", "#t_popover", None),
            ("tooltip", "#t_tooltip", None),
            ("dropdown", "#t_dropdown", None),
            ("hovercard", "#t_hover", None),
        ]:
            before = clicks()
            page.mouse.move(5, 5)
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
            try:
                page.click(sel, timeout=5000)
            except Exception as e:
                p(f"{name}: CLICK FAILED {type(e).__name__}: {str(e)[:200]}")
            page.wait_for_timeout(1200)
            after = clicks()
            p(f"REALCLICK {name}: {before} -> {after} log={logv()}  {'OK' if after != before else 'NO-EVENT'}")
            page.keyboard.press("Escape")
            page.wait_for_timeout(400)

        # dropdown: second consecutive real click
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
        before = clicks()
        page.click("#t_dropdown")
        page.wait_for_timeout(1200)
        p(f"REALCLICK dropdown(2nd): {before} -> {clicks()}")
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)

        # dropdown: programmatic .click() (no pointer events, bypasses radix pointerdown)
        before = clicks()
        page.eval_on_selector("#t_dropdown", "el => el.click()")
        page.wait_for_timeout(1200)
        after = clicks()
        p(f"JSCLICK dropdown: {before} -> {after} log={logv()}  "
          f"{'handler-wired-OK' if after != before else 'handler-MISSING'}")
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)

        # dropdown: keyboard activation (focus + Enter)
        before = clicks()
        page.focus("#t_dropdown")
        page.keyboard.press("Enter")
        page.wait_for_timeout(1200)
        p(f"KEYBOARD dropdown Enter: {before} -> {clicks()} log={logv()}")
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)

        # dropdown: did the menu actually open on the real click? and DOM shape
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        page.click("#t_dropdown")
        page.wait_for_timeout(800)
        menu_open = page.locator("#dd_item").count()
        body_pe = page.evaluate("getComputedStyle(document.body).pointerEvents")
        p(f"DROPDOWN menu item present after click: {menu_open}; body pointer-events={body_pe}")
        shape = page.evaluate(
            """() => {
                 const b = document.querySelector('#t_dropdown');
                 const out = [];
                 let e = b;
                 for (let i=0; i<4 && e; i++) { out.push(e.tagName + '.' + (e.className||'').slice(0,60)); e = e.parentElement; }
                 return out;
               }"""
        )
        p("DROPDOWN ancestry:", json.dumps(shape))
        dlg_shape = page.evaluate(
            """() => {
                 const b = document.querySelector('#t_dialog');
                 const out = [];
                 let e = b;
                 for (let i=0; i<4 && e; i++) { out.push(e.tagName + '.' + (e.className||'').slice(0,60)); e = e.parentElement; }
                 return out;
               }"""
        )
        p("DIALOG ancestry:", json.dumps(dlg_shape))
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        page.screenshot(path=f"{OUT}/triggers_dropdown.png")

        # ---------- forms ----------
        page.goto(f"{BASE}/forms", wait_until="networkidle")
        page.wait_for_timeout(1500)
        page.fill("#inp_name", "Ada Lovelace")
        page.wait_for_timeout(200)
        page.fill("#inp_ctl", "ctl-typed")
        page.wait_for_timeout(200)
        page.fill("#inp_nick", "nick-typed")
        page.wait_for_timeout(200)
        page.fill("#inp_bio", "bio text")
        page.wait_for_timeout(300)
        # select
        try:
            page.click("#inp_fruit")
            page.wait_for_timeout(600)
            page.get_by_role("option", name="banana").click()
            page.wait_for_timeout(800)
            page.keyboard.press("Escape")
            page.wait_for_timeout(600)
        except Exception as e:
            p("select failed", type(e).__name__, str(e)[:200])
            page.keyboard.press("Escape")
            page.wait_for_timeout(600)
        try:
            page.click("#inp_agree", force=True)
            page.wait_for_timeout(400)
            page.click("#inp_notify", force=True)
            page.wait_for_timeout(400)
            page.get_by_text("green", exact=True).click(force=True)
            page.wait_for_timeout(400)
        except Exception as e:
            p("toggles failed", type(e).__name__, str(e)[:150])
        page.screenshot(path=f"{OUT}/forms_filled.png")
        page.click("#btn_submit", force=True)
        page.wait_for_timeout(2500)
        submitted = txt(page, "#out_submitted")
        p("SUBMITTED=", submitted)
        page.screenshot(path=f"{OUT}/forms_submitted.png")

        p("CONSOLE/PAGE ERRORS (" + str(len(errs)) + "):")
        for e in errs[:25]:
            p("  " + e[:300])

        ctx.close()
        b.close()


try:
    main()
finally:
    pass
