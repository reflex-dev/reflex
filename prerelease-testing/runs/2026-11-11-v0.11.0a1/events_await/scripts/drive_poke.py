"""Out-of-band `app.modify_state` + awaited handlers: open the page, call /poke/<token>, watch the page.

usage: drive_poke.py <frontend_url> <backend_url>
"""
import json
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

FE, BE = sys.argv[1].rstrip("/"), sys.argv[2].rstrip("/")
IDS = ["result", "total", "doubled", "progress", "other-items", "secret_runs", "blocked-count"]
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = browser.new_context().new_page()
    console = []
    page.on("console", lambda m: console.append((m.type, m.text[:200])))
    page.goto(FE + "/")
    page.wait_for_function("() => (document.getElementById('token')?.textContent ?? '').length > 10", timeout=30000)
    time.sleep(1)
    token = page.inner_text("#token")
    page.click("#b-reset")
    time.sleep(0.8)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    t0 = time.time()
    with opener.open(f"{BE}/poke/{token}", timeout=30) as r:
        body = json.loads(r.read())
    print("poke response:", json.dumps(body), f"({time.time() - t0:.2f}s)")
    time.sleep(1.0)
    snap = page.evaluate("(ids) => Object.fromEntries(ids.map(i => [i, document.getElementById(i)?.textContent ?? null]))", IDS)
    print("page after poke:", snap)
    print("toasts:", page.evaluate("() => [...document.querySelectorAll('[data-sonner-toast]')].map(t => t.textContent)"))
    page.click("#b-ping")
    time.sleep(0.8)
    print("after ping:", page.inner_text("#result"))
    print("console errors:", [c for c in console if c[0] in ("error", "warning")])
    browser.close()
