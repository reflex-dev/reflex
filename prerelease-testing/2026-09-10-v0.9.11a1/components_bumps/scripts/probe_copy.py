"""Click the shiki code block copy button and read the clipboard back."""
import sys
from playwright.sync_api import sync_playwright

url = sys.argv[1]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    ctx.grant_permissions(["clipboard-read", "clipboard-write"])
    pg = ctx.new_page()
    errs = []
    pg.on("console", lambda m: errs.append(m.text[:150]) if m.type == "error" else None)
    pg.goto(url, wait_until="networkidle")
    pg.wait_for_timeout(3500)
    btn = pg.query_selector("#xcb-python button")
    print("copy button found:", btn is not None)
    if btn:
        btn.scroll_into_view_if_needed()
        btn.click()
        pg.wait_for_timeout(1200)
        print("clipboard:", repr(pg.evaluate("() => navigator.clipboard.readText()")))
        print("svg after click:", pg.eval_on_selector("#xcb-python button svg", "el => el.innerHTML.slice(0,60)"))
    print("console errors:", errs)
    b.close()
