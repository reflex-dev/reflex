"""Minimal repro: a computed var clears a LocalStorage value during hydration; does the browser see it?

Usage: drive_storage_only.py <base_url>   (tp_patterns app, /storage page)
Prints one line: RESULT tp_ls_cv=<localStorage value> ui=<rendered> cv=<computed var>
"""
import sys

from tpdrive import browser, wait_text

BASE = sys.argv[1].rstrip("/")
with browser() as b:
    ctx = b.new_context()
    page = ctx.new_page()
    page.goto(BASE + "/storage", wait_until="networkidle")
    wait_text(page, "#store_log", "on_load")
    page.evaluate("() => localStorage.setItem('tp_ls_cv', 'bad')")
    page.goto(BASE + "/storage", wait_until="networkidle")
    wait_text(page, "#store_log", "on_load")
    page.wait_for_timeout(2000)
    ls = page.evaluate("() => localStorage.getItem('tp_ls_cv')")
    ui = page.locator("#ls_cv").inner_text()
    cv = page.locator("#cv_check").inner_text()
    # a second, plain reload: does the backend keep re-clearing a value the browser keeps resending?
    page.reload(wait_until="networkidle")
    wait_text(page, "#store_log", "on_load")
    page.wait_for_timeout(1500)
    ls2 = page.evaluate("() => localStorage.getItem('tp_ls_cv')")
    print(f"RESULT tp_ls_cv={ls!r} ui={ui!r} cv={cv!r} after_2nd_reload_tp_ls_cv={ls2!r}")
