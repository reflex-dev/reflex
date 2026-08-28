"""Extra probes: 404-prefix on_load misfire (#6790 backend matcher) and
button-started background task surviving navigation.

Usage: python drive_extra.py [base_url] [shots_dir]
"""

import json
import os
import sys

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
    ctx = browser.new_context()

    # Probe 1: /posts-archive shares the catchall's prefix but has no page.
    # Backend route matcher must NOT resolve it to posts/[[...splat]] and
    # fire the catchall's on_load (the actual #6790 failure mode).
    page = ctx.new_page()
    console = []
    page.on("console", lambda m: console.append((m.type, m.text)))
    page.goto(BASE + "/posts-archive", wait_until="load", timeout=30000)
    page.wait_for_timeout(2500)
    body_404 = page.inner_text("body")[:200].replace("\n", " | ")
    page.screenshot(path=f"{SHOTS}/13_posts_archive_404.png")
    # go to a real page to read the visits state for this token
    page.goto(BASE + "/other", wait_until="load", timeout=30000)
    page.wait_for_selector("#visits", state="attached", timeout=15000)
    page.wait_for_function(
        "() => document.querySelector('#visits').innerText.includes('|other|')",
        timeout=10000,
    )
    visits = page.locator("#visits").inner_text()
    misfire = "posts-catchall|path=/posts-archive" in visits
    record(
        "splat-6790-prefix-404-no-onload-misfire",
        "fail" if misfire else "pass",
        f"goto /posts-archive (no page; body={body_404!r}), then /other; "
        f"visits={visits!r} — a 'posts-catchall|path=/posts-archive' entry means the "
        "backend matched the catchall for a mere prefix path and fired its on_load",
    )
    page.close()

    # Probe 2: background task started from a BUTTON must survive navigation
    # (only superseded chains, e.g. on_load, are cancelled).
    page = ctx.new_page()
    page.goto(BASE + "/slowbg", wait_until="load", timeout=30000)
    page.wait_for_selector("#btn-bg-click", state="attached", timeout=15000)
    # let the on_load bg task finish so its entries don't confuse the check
    page.wait_for_timeout(5000)
    page.click("#btn-clear-bg")
    page.wait_for_timeout(400)
    page.click("#btn-bg-click")
    page.wait_for_function(
        "() => document.querySelector('#bg-progress').innerText.includes('btnbg-start')",
        timeout=8000,
    )
    page.click("#nav-other")
    page.wait_for_function(
        "() => document.querySelector('#page-heading').innerText === 'OTHER'",
        timeout=8000,
    )
    page.wait_for_timeout(5500)
    bg = page.locator("#bg-progress").inner_text()
    page.screenshot(path=f"{SHOTS}/14_btnbg_after_nav.png")
    survived = "btnbg-step4" in bg
    record(
        "background-task-from-button-survives-nav",
        "pass" if survived else "fail",
        f"clicked start-bg button on /slowbg, navigated to /other during its 4s run; "
        f"bg_progress={bg!r} — button-started background task "
        f"{'completed all steps (survived)' if survived else 'STOPPED after navigation'}",
    )
    page.close()
    browser.close()

print("RESULTS_JSON:" + json.dumps(results))
