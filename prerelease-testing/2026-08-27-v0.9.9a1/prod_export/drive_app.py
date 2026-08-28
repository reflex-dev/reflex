"""Playwright driver for the prod_export cluster app.

Usage:
    python drive_app.py <base_url> <out_prefix> [--skip-dynamic-direct]

Performs a full browser pass: hydration, counter events, input+event chain,
foreach updates, env-mode check, client-side navigation (rx.link + custom
react-router NavLink), dynamic route param, direct-load of a dynamic route.
Captures console messages, page errors, failed responses, and screenshots.
Exits 0 on success; prints a JSON summary to stdout (last line).
"""

import json
import sys
import time

from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
PREFIX = sys.argv[2]
SKIP_DYNAMIC_DIRECT = "--skip-dynamic-direct" in sys.argv

console_msgs = []
page_errors = []
bad_responses = []
failures = []

BENIGN_SNIPPETS = (
    "HydrateFallback",
    "[vite] connecting",
    "[vite] connected",
    "React DevTools",
    "Download the React DevTools",
)


def check(name, cond, detail=""):
    """Record a check result."""
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name} {detail}")
    if not cond:
        failures.append(f"{name}: {detail}")


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = browser.new_context()
    page = ctx.new_page()

    page.on(
        "console",
        lambda m: console_msgs.append({"type": m.type, "text": m.text}),
    )
    page.on("pageerror", lambda e: page_errors.append(str(e)))
    page.on(
        "response",
        lambda r: bad_responses.append({"url": r.url, "status": r.status})
        if r.status >= 400
        else None,
    )

    page.goto(BASE + "/", wait_until="networkidle")
    page.wait_for_selector("#count-display", timeout=30000)
    # Wait for websocket hydration: click + and expect count change.
    page.screenshot(path=f"{PREFIX}_index_initial.png", full_page=True)

    check("index title", "Home | prodapp" in page.title(), page.title())

    # Counter events.
    page.click("#btn-inc")
    try:
        page.wait_for_function(
            "document.querySelector('#count-display').innerText === '1'",
            timeout=15000,
        )
        check("counter increments", True)
    except Exception:
        check(
            "counter increments",
            False,
            f"count-display={page.inner_text('#count-display')!r}",
        )
    for _ in range(4):
        page.click("#btn-inc")
    page.wait_for_function(
        "document.querySelector('#count-display').innerText === '5'",
        timeout=15000,
    )
    check("cond flips to big badge", page.is_visible("#big-badge"))
    page.click("#btn-dec")
    page.wait_for_function(
        "document.querySelector('#count-display').innerText === '4'",
        timeout=15000,
    )

    # Input + add item (foreach) + event chain.
    page.fill("#item-input", "gamma")
    page.click("#btn-add")
    page.wait_for_function(
        "document.querySelectorAll('.item-row').length === 3", timeout=15000
    )
    items = page.eval_on_selector_all(
        ".item-row", "els => els.map(e => e.innerText)"
    )
    check("foreach shows added item", items == ["alpha", "beta", "gamma"], str(items))
    chain = page.inner_text("#chain-log")
    check("event chain ran", "add_item done" in chain, chain)
    check("input cleared after add", page.input_value("#item-input") == "")

    # Env mode as seen by backend.
    page.click("#btn-envmode")
    page.wait_for_function(
        "document.querySelector('#envmode-display').innerText.length > 'env_mode='.length",
        timeout=15000,
    )
    envmode = page.inner_text("#envmode-display")
    print(f"[INFO] backend env mode display: {envmode!r}")

    # Custom react-router hook component.
    badge = page.inner_text("#location-badge")
    check("useLocation badge on index", badge == "/", badge)

    page.screenshot(path=f"{PREFIX}_index_after.png", full_page=True)

    # Client-side navigation via rx.link.
    page.click("#nav-about")
    page.wait_for_selector("#about-heading", timeout=15000)
    check("about canary", page.is_visible("#about-canary"))
    badge = page.inner_text("#location-badge")
    check("useLocation badge on about", badge == "/about", badge)
    check("about title", "About | prodapp" in page.title(), page.title())
    page.screenshot(path=f"{PREFIX}_about.png", full_page=True)

    # Back home, then dynamic route via link.
    page.click("#nav-home")
    page.wait_for_selector("#main-heading", timeout=15000)
    count_after_nav = page.inner_text("#count-display")
    check("state preserved across nav", count_after_nav == "4", count_after_nav)

    page.click("#nav-post1")
    page.wait_for_selector("#post-heading", timeout=15000)
    page.wait_for_function(
        "document.querySelector('#post-pid').innerText === 'pid=1'", timeout=15000
    )
    check("dynamic route pid=1", True)
    visits = page.inner_text("#post-visits")
    check("on_load fired for post", visits == "visits=1", visits)

    page.click("#nav-post42")
    page.wait_for_function(
        "document.querySelector('#post-pid').innerText === 'pid=42'", timeout=15000
    )
    check("dynamic route pid=42 (client-side param change)", True)
    visits = page.inner_text("#post-visits")
    check("on_load re-fired for new pid", visits == "visits=2", visits)
    page.screenshot(path=f"{PREFIX}_post42.png", full_page=True)

    # Custom NavLink component navigation.
    page.click("#nav-navlink-about")
    page.wait_for_selector("#about-heading", timeout=15000)
    check("custom NavLink navigates", True)

    # Direct load of a dynamic route (fresh document request).
    if not SKIP_DYNAMIC_DIRECT:
        page.goto(BASE + "/post/7", wait_until="networkidle")
        try:
            page.wait_for_function(
                "document.querySelector('#post-pid') && document.querySelector('#post-pid').innerText === 'pid=7'",
                timeout=20000,
            )
            check("direct-load dynamic route pid=7", True)
        except Exception:
            body = page.content()[:500]
            check("direct-load dynamic route pid=7", False, body)
        page.screenshot(path=f"{PREFIX}_post7_direct.png", full_page=True)

    # Direct load of a non-existent page -> 404 route.
    page.goto(BASE + "/definitely-not-a-page", wait_until="networkidle")
    page.screenshot(path=f"{PREFIX}_404.png", full_page=True)
    print(f"[INFO] 404 page title: {page.title()!r}")

    browser.close()

unexpected_console = [
    m
    for m in console_msgs
    if m["type"] in ("error", "warning")
    and not any(s in m["text"] for s in BENIGN_SNIPPETS)
]

summary = {
    "failures": failures,
    "page_errors": page_errors,
    "unexpected_console": unexpected_console,
    "bad_responses": bad_responses,
    "all_console_count": len(console_msgs),
}
with open(f"{PREFIX}_console.json", "w") as f:
    json.dump({"console": console_msgs, "summary": summary}, f, indent=2)
print("SUMMARY:" + json.dumps(summary))
sys.exit(1 if failures else 0)
