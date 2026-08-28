"""Focused verifier driver for the /_reflex/cookies/sync 404 claim.

Usage: python drive_cookie_sync.py <frontend_base> <backend_base> <shots_dir>

Sequence:
1. Load index, click "Cookie Sync" -> record status of the POST to
   /_reflex/cookies/sync (claim: 404).
2. Click "Login with Okta" -> mock IdP /authorize; then hit the callback with a
   bogus code (exercises the backend token-exchange failure path, which may run
   HTTPCookie.sync() inside the serving worker and register the route lazily).
3. Reload index, click "Cookie Sync" again -> record status (if now != 404, the
   lazy in-worker registration mechanism is confirmed).
"""

import json
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from playwright.sync_api import sync_playwright

FRONTEND = sys.argv[1].rstrip("/")
BACKEND = sys.argv[2].rstrip("/")
SHOTS = Path(sys.argv[3])
SHOTS.mkdir(parents=True, exist_ok=True)

results = []
sync_responses = []
console_lines = []
page_errors = []


def check(name, ok, details=""):
    results.append({"name": name, "ok": bool(ok), "details": str(details)[:500]})
    print(f"RESULT {'PASS' if ok else 'FAIL'} {name} :: {str(details)[:500]}")


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    page.on("console", lambda m: console_lines.append(f"{m.type}: {m.text}"))
    page.on("pageerror", lambda e: page_errors.append(str(e)))
    page.on(
        "response",
        lambda r: sync_responses.append((r.status, r.url))
        if "/_reflex/cookies/sync" in r.url
        else None,
    )

    page.goto(FRONTEND + "/", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3000)
    page.screenshot(path=str(SHOTS / "01_index.png"), full_page=True)

    n_before = len(sync_responses)
    page.locator("button", has_text="Cookie Sync").click()
    page.wait_for_timeout(2000)
    first = sync_responses[n_before:]
    check(
        "cookie_sync_click_fresh_worker",
        len(first) == 1,
        f"responses={first}",
    )
    first_status = first[0][0] if first else None

    # Okta login -> bogus-code callback to run backend failure path.
    okta_params = {}
    try:
        page.locator("button", has_text="Login with Okta").first.click()
        page.wait_for_url("**/authorize*", timeout=20000)
        okta_params = dict(parse_qsl(urlsplit(page.url).query))
        cb = f"{okta_params['redirect_uri']}?code=bogus-code&state={okta_params['state']}"
        page.goto(cb, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)
        page.screenshot(path=str(SHOTS / "02_callback.png"), full_page=True)
        check("okta_bogus_callback_ran", True, f"final_url={page.url[:150]}")
    except Exception as e:  # noqa: BLE001
        check("okta_bogus_callback_ran", False, f"exception: {e}")

    page.goto(FRONTEND + "/", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(2000)
    n_before = len(sync_responses)
    page.locator("button", has_text="Cookie Sync").click()
    page.wait_for_timeout(2000)
    second = sync_responses[n_before:]
    check(
        "cookie_sync_click_after_callback",
        len(second) >= 1,
        f"responses={second}",
    )
    second_status = second[0][0] if second else None

    print(f"FIRST_SYNC_STATUS={first_status}")
    print(f"SECOND_SYNC_STATUS={second_status}")
    browser.close()

(SHOTS / "results.json").write_text(
    json.dumps(
        {
            "results": results,
            "sync_responses": sync_responses,
            "console_lines": console_lines,
            "page_errors": page_errors,
        },
        indent=2,
    )
)
