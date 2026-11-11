"""Issue 4 (and 3's browser side): click each ret_* button in vapp, report page state, console and new log lines.

usage: v4_drive_returns.py <frontend_url> <server_log> [png]
"""
import sys
import time

from playwright.sync_api import sync_playwright

url, log = sys.argv[1], sys.argv[2]
png = sys.argv[3] if len(sys.argv) > 3 else None


def log_size():
    with open(log, errors="replace") as f:
        return len(f.read())


with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    msgs = []
    pg.on("console", lambda m: msgs.append(f"{m.type}: {m.text[:200]}"))
    pg.goto(url)
    pg.wait_for_function("document.querySelector('#total') && document.querySelector('#total').innerText.includes('=')", timeout=90000)
    time.sleep(2)
    token = pg.evaluate("window.sessionStorage.getItem('token')")
    print("browser token:", token, "| page total on load:", pg.inner_text("#total"))
    for bid in ["ret_value", "ret_garbage", "ret_self_handler", "ret_class_handler"]:
        start = log_size()
        pg.click(f"#{bid}")
        time.sleep(1.5)
        with open(log, errors="replace") as f:
            new = f.read()[start:]
        errs = [l.strip()[:230] for l in new.splitlines() if "Error" in l or "must only return" in l]
        toasts = pg.locator("[data-sonner-toast]").all_inner_texts()
        print(f"{bid:18s} last={pg.inner_text('#last')!r:32s} b={pg.inner_text('#b')!r:6s} toasts={[t[:60] for t in toasts]} log={errs[-1:] }")
    if png:
        pg.screenshot(path=png)
    print("console warnings/errors:", [m for m in msgs if m.startswith(("error", "warning"))])
    b.close()
