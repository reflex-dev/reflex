"""Browser back/forward navigation across catchall/static/dynamic routes.

Usage: python drive_backforward.py [base_url] [shots_dir]
"""

import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:3100"
SHOTS = sys.argv[2] if len(sys.argv) > 2 else "shots"
os.makedirs(SHOTS, exist_ok=True)

results = []


def record(name, status, details):
    results.append({"name": name, "status": status, "details": details})
    print(f"== {name}: {status} :: {details}", flush=True)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = browser.new_context().new_page()
    console = []
    page.on("console", lambda m: console.append((m.type, m.text)))

    def heading():
        return page.locator("#page-heading").inner_text(timeout=5000)

    page.goto(BASE + "/postsomething", wait_until="load", timeout=30000)
    page.wait_for_selector("#visits", state="attached", timeout=15000)
    page.wait_for_timeout(1000)
    # client-side navs: postsomething -> posts catchall -> articles/all/5 -> articles/9
    page.click("#nav-posts")
    page.wait_for_timeout(700)
    page.click("#nav-art-all-5")
    page.wait_for_timeout(700)
    page.click("#nav-art-2")
    page.wait_for_timeout(700)
    h_before = heading()

    seq = []
    for step in ["back", "back", "back", "forward", "forward"]:
        getattr(page, "go_" + step)()
        page.wait_for_timeout(900)
        seq.append((step, page.url.replace(BASE, ""), heading()))

    visits = page.locator("#visits").inner_text()
    page.screenshot(path=f"{SHOTS}/12_backforward.png")
    expected = [
        ("back", "/articles/all/5", "ARTICLES-ALL-STATIC"),
        ("back", "/posts", "POSTS-CATCHALL"),
        ("back", "/postsomething", "POSTSOMETHING"),
        ("forward", "/posts", "POSTS-CATCHALL"),
        ("forward", "/articles/all/5", "ARTICLES-ALL-STATIC"),
    ]
    ok = seq == expected
    record(
        "back-forward-route-resolution",
        "pass" if ok else "fail",
        f"start={h_before!r}; history walk={seq}; expected={expected}; visits={visits!r}",
    )
    bad_console = [
        f"[{t}] {m}"
        for t, m in console
        if t in ("error", "pageerror", "warning")
        and not any(
            b in m
            for b in ("HydrateFallback", "[vite]", "React DevTools", "Download the React DevTools")
        )
    ]
    if bad_console:
        record("back-forward-console", "anomaly", f"console: {bad_console}")
    browser.close()

print("RESULTS_JSON:" + json.dumps(results))
