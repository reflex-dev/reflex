"""Click each return-value button on a fresh /fail page; report visible toast text, console errors/warnings, failed requests.

usage: p7_toast_each.py <frontend_url> <png_prefix> <name> [name ...]
"""
import sys
import time

from playwright.sync_api import sync_playwright

url, prefix, names = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3:]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for n in names:
        pg = b.new_page()
        cons, bad = [], []
        pg.on("console", lambda m: cons.append(f"{m.type}: {m.text[:200]}") if m.type in ("error", "warning") else None)
        pg.on("pageerror", lambda e: cons.append(f"pageerror: {str(e)[:200]}"))
        pg.on("response", lambda r: bad.append(f"{r.status} {r.url}") if r.status >= 400 else None)
        pg.goto(url + "/fail")
        pg.wait_for_selector(f"#f-{n}", timeout=60000)
        time.sleep(1.5)
        pg.click(f"#f-{n}")
        time.sleep(2)
        t = [e.inner_text()[:260].replace("\n", " ") for e in pg.query_selector_all("[data-sonner-toast]")]
        pg.screenshot(path=f"{prefix}_{n}.png")
        print(f"{n}: toasts={t} console={cons} bad={bad}", flush=True)
        pg.close()
    b.close()
