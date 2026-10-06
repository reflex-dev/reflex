"""Measure disclosure and mutation after real logout cleanup failures."""

import hashlib
import json
import logging
import re
import sys
import traceback
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

ROOT = Path(__file__).resolve().parent
BASE = "http://localhost:3152"
LOGGER = logging.getLogger(__name__)


def snapshot(page: Page) -> dict:
    """Capture visible app values and a hashed Reflex client token.

    Args:
        page: The current browser page.

    Returns:
        Visible fields and a token fingerprint without credentials.
    """
    token = page.evaluate("sessionStorage.getItem('token')")
    return {
        "url": page.url.split("?")[0],
        "token_fingerprint": hashlib.sha256(token.encode()).hexdigest() if token else None,
        "fields": {name: page.locator("#" + name).inner_text() for name in ("identity", "private-record", "private-cache", "calls", "last-actor", "armed") if page.locator("#" + name).count()},
    }


def cookie_summary(context) -> list[dict]:
    """Record cookie flags without values.

    Args:
        context: The isolated Playwright browser context.

    Returns:
        Cookie metadata and value lengths.
    """
    return [{key: value for key, value in item.items() if key != "value"} | {"value_length": len(item["value"])} for item in context.cookies()]


def action_records() -> list[dict]:
    """Read the app's independent mutation audit.

    Returns:
        Nonsecret actor/counter entries written by successful protected actions.
    """
    path = ROOT / "logs/actions.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def login(page: Page, user: str) -> None:
    """Complete a normal OIDC login as one predefined user.

    Args:
        page: The browser page.
        user: The mock subject to authenticate.
    """
    page.get_by_role("button", name="Login with Generic").click()
    page.wait_for_url(re.compile("/oauth2/authorize"))
    page.locator(f'button[name="sub"][value="{user}"]').click()
    page.wait_for_url(lambda url: url.startswith(BASE) and "callback" not in url)
    if "/profile" not in page.url:
        page.goto(BASE + "/profile")
    expect(page.locator("#identity")).to_have_text(user)


def main() -> None:
    """Run frontend/backend dependency outages and a normal logout control."""
    label = sys.argv[1] if len(sys.argv) > 1 else "a4"
    (ROOT / "screenshots").mkdir(exist_ok=True)
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for mode in ("normal", "frontend", "backend"):
            for name in ("frontend-unavailable", "backend-unavailable"):
                (ROOT / name).unlink(missing_ok=True)
            context = browser.new_context()
            page = context.new_page()
            page.set_default_timeout(15000)
            result = {"case": mode, "stage": "initial", "browser_version": browser.version, "console": [], "page_errors": [], "failed_requests": [], "http_errors": [], "wire_markers": []}
            page.on("console", lambda message, target=result: target["console"].append({"type": message.type, "text": message.text}))
            page.on("pageerror", lambda error, target=result: target["page_errors"].append(str(error)))
            page.on("requestfailed", lambda request, target=result: target["failed_requests"].append({"url": request.url.split("?")[0], "failure": request.failure}))
            page.on("response", lambda response, target=result: target["http_errors"].append({"url": response.url.split("?")[0], "status": response.status}) if response.status >= 400 else None)
            page.on("websocket", lambda socket, target=result: socket.on("framereceived", lambda data: target["wire_markers"].append({"stage": target["stage"], "alice_record": "alice-PRIVATE-RECORD" in str(data), "alice_cache": "alice-PRIVATE-CACHE" in str(data), "bytes": len(data)}) if "PRIVATE" in str(data) else None))
            try:
                page.goto(BASE + "/profile")
                login(page, "alice")
                page.get_by_role("button", name="Prime private data", exact=True).click()
                expect(page.locator("#private-record")).to_contain_text("alice-PRIVATE-RECORD")
                expect(page.locator("#private-cache")).to_have_text("alice-PRIVATE-CACHE")
                result["alice_before"] = snapshot(page)
                before = len(action_records())
                if mode != "normal":
                    page.get_by_role("button", name=f"Arm {mode} outage", exact=True).click()
                    expect(page.locator("#armed")).to_have_text(mode)
                result["stage"] = "logout"
                page.get_by_role("button", name="Logout", exact=True).click()
                if mode == "normal":
                    page.wait_for_url(re.compile("/oauth2/end_session"))
                    page.get_by_role("button", name="End session", exact=True).click()
                    page.wait_for_url(lambda url: url.split("?")[0] == BASE + "/")
                else:
                    expect(page.get_by_text("Logout error", exact=True)).to_be_visible()
                    page.wait_for_timeout(2000)
                result["after_logout"] = snapshot(page)
                result["cookies_after_logout"] = cookie_summary(context)
                result["stage"] = "post_logout_protected_action"
                if page.locator("#identity").count():
                    page.get_by_role("button", name="Protected action", exact=True).click()
                    page.wait_for_timeout(2000)
                result["actions_after_logout"] = action_records()[before:]
                result["after_logout_action"] = snapshot(page)
                result["stage"] = "forced_anonymous"
                context.clear_cookies()
                page.goto(BASE + "/")
                page.wait_for_timeout(1000)
                result["forced_anonymous"] = snapshot(page)
                anonymous_before = len(action_records())
                page.get_by_role("button", name="Protected action", exact=True).click()
                page.wait_for_url(re.compile("/login"))
                result["anonymous_mutations"] = action_records()[anonymous_before:]
                result["pending_present"] = bool(page.evaluate("sessionStorage.getItem('rxe_auth_pending_event')"))
                for name in ("frontend-unavailable", "backend-unavailable"):
                    (ROOT / name).unlink(missing_ok=True)
                result["stage"] = "bob_login"
                login(page, "bob")
                page.wait_for_timeout(1500)
                result["bob_after"] = snapshot(page)
                body = page.inner_text("body")
                result["bob_observed_alice_record"] = "alice-PRIVATE-RECORD" in body
                result["bob_observed_alice_cache"] = "alice-PRIVATE-CACHE" in body
                result["same_client_token"] = result["alice_before"]["token_fingerprint"] == result["bob_after"]["token_fingerprint"]
                result["pending_cleared_after_bob"] = not page.evaluate("sessionStorage.getItem('rxe_auth_pending_event')")
                result["actions_after_bob"] = action_records()[before:]
                result["completed"] = True
                page.screenshot(path=str(ROOT / "screenshots" / f"{label}-{mode}-bob.png"), full_page=True)
            except Exception:
                LOGGER.exception("Logout boundary case %s failed", mode)
                result["completed"] = False
                result["traceback"] = traceback.format_exc()
                result["last_snapshot"] = snapshot(page)
                page.screenshot(path=str(ROOT / "screenshots" / f"{label}-{mode}-setup-failure.png"), full_page=True)
            results.append(result)
            (ROOT / "logs" / f"faults-{label}.json").write_text(json.dumps(results, indent=2))
            print(json.dumps({key: value for key, value in result.items() if key not in {"console", "wire_markers", "cookies_after_logout"}}), flush=True)
            context.close()
        browser.close()
    assert all(result["completed"] for result in results), "Security observations did not complete"


if __name__ == "__main__":
    main()
