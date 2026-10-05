"""Capture the OIDC logout failure after proving login and identity delivery."""

import argparse
import json
import re
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent


def main() -> None:
    """Login, click logout, capture its result, and require provider navigation."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:3132")
    args = parser.parse_args()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(args.base_url + "/profile")
        page.wait_for_url(re.compile("/login"))
        page.get_by_role("button", name="Login with Generic").click()
        page.wait_for_url(re.compile("/oauth2/authorize"))
        page.locator('button[name="sub"][value="alice"]').click()
        page.wait_for_url(args.base_url + "/profile")
        expect(page.locator("#name")).to_have_text("Alice Admin")
        expect(page.locator("#email")).to_have_text("alice@example.com")
        page.get_by_role("button", name="Reveal", exact=True).click()
        expect(page.locator("#message")).to_have_text("revealed-alice")
        page.get_by_role("button", name="Logout", exact=True).click()
        page.wait_for_function(
            "() => document.body.innerText.includes('Logout error') || location.pathname.includes('end_session')"
        )
        failed = page.get_by_text("Logout error", exact=True).is_visible()
        if failed:
            page.wait_for_function(
                "() => { const toast = document.querySelector('[data-sonner-toast]'); return toast && toast.getBoundingClientRect().bottom <= innerHeight && Number(getComputedStyle(toast).opacity) > 0.95; }"
            )
        result = {
            "url": page.url.split("?")[0],
            "logout_error_visible": failed,
            "name_still_visible": page.locator("#name").is_visible()
            if failed
            else False,
        }
        page.screenshot(path=str(ROOT / "screenshots/oidc-logout-error-alpha.png"))
        if failed:
            page.get_by_role("button", name="Reveal", exact=True).click()
            page.wait_for_function(
                "() => location.pathname.includes('login') || document.querySelector('#message')?.textContent.startsWith('revealed-')"
            )
            result["protected_event_after_logout"] = {
                "url": page.url.split("?")[0],
                "message": page.locator("#message").inner_text()
                if page.locator("#message").count()
                else None,
            }
            page.goto(args.base_url + "/profile")
            page.wait_for_function(
                "() => location.pathname.includes('login') || document.querySelector('#name')?.textContent === 'Alice Admin'"
            )
            result["profile_after_navigation"] = {
                "url": page.url.split("?")[0],
                "name": page.locator("#name").inner_text()
                if page.locator("#name").count()
                else None,
            }
        (ROOT / "logs/repro-logout-alpha.json").write_text(json.dumps(result, indent=2))
        print(json.dumps(result))
        browser.close()
        assert not failed, "Logout failed and left the authenticated profile visible"


if __name__ == "__main__":
    main()
