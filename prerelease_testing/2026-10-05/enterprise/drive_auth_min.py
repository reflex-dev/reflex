"""Drive default AuthPlugin and normalized profile vars on the alpha."""

import json
import re
import traceback
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent
BASE = "http://localhost:3132"


def authorize(page, user: str = "alice") -> None:
    """Complete one login through the local mock provider.

    Args:
        page: Browser page displaying the login palette.
        user: Mock user's subject.
    """
    page.get_by_role("button", name="Login with Generic").click()
    page.wait_for_url(re.compile("/oauth2/authorize"))
    page.locator(f'button[name="sub"][value="{user}"]').click()


def main() -> None:
    """Check login, profile, protected events, refresh, logout and popup auth."""
    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        for case in [
            "profile_login_reveal_logout",
            "anonymous_event_replay",
            "iframe_popup",
        ]:
            context = browser.new_context()
            page = context.new_page()
            page.set_default_timeout(20_000)
            console, errors = [], []
            page.on(
                "console",
                lambda msg, target=console: target.append({
                    "type": msg.type,
                    "text": msg.text,
                }),
            )
            page.on("pageerror", lambda error, target=errors: target.append(str(error)))
            try:
                if case == "profile_login_reveal_logout":
                    page.goto(BASE + "/profile")
                    page.wait_for_url(re.compile("/login"))
                    authorize(page)
                    page.wait_for_url(BASE + "/profile")
                    expect(page.locator("#name")).to_have_text("Alice Admin")
                    expect(page.locator("#email")).to_have_text("alice@example.com")
                    page.get_by_role("button", name="Reveal", exact=True).click()
                    expect(page.locator("#message")).to_have_text("revealed-alice")
                    page.screenshot(
                        path=str(ROOT / "screenshots/auth-min-alpha-profile.png")
                    )
                    page.get_by_role("button", name="Logout", exact=True).click()
                    page.wait_for_url(re.compile("/oauth2/end_session"))
                    page.get_by_role("button", name="End session", exact=True).click()
                    page.wait_for_url(BASE + "/")
                    page.goto(BASE + "/profile")
                    page.wait_for_url(re.compile("/login"))
                elif case == "anonymous_event_replay":
                    page.goto(BASE)
                    page.get_by_role("button", name="Reveal", exact=True).click()
                    page.wait_for_url(re.compile("/login"))
                    authorize(page)
                    page.wait_for_url(BASE + "/")
                    expect(page.locator("#message")).to_have_text("revealed-alice")
                    assert not page.evaluate(
                        "sessionStorage.getItem('rxe_auth_pending_event')"
                    )
                elif case == "iframe_popup":
                    page.goto(BASE + "/iframe")
                    frame = page.frame_locator("iframe")
                    with page.expect_popup() as opened:
                        frame.get_by_role(
                            "button", name="Login with Generic", exact=True
                        ).click()
                    popup = opened.value
                    popup.wait_for_url(re.compile("/oauth2/authorize"))
                    popup.locator('button[name="sub"][value="alice"]').click()
                    popup.wait_for_event("close")
                    expect(frame.locator("#signed-in")).to_have_text("Signed in")
                    frame.get_by_role("button", name="Reveal", exact=True).click()
                    expect(frame.locator("#message")).to_have_text("revealed-alice")
                assert not errors, errors
                result = {"case": case, "passed": True}
            except Exception:
                result = {
                    "case": case,
                    "passed": False,
                    "traceback": traceback.format_exc(),
                    "url": page.url.split("?")[0],
                }
                page.screenshot(
                    path=str(ROOT / "screenshots" / f"auth-min-{case}-failure.png")
                )
            result.update(console=console, page_errors=errors)
            results.append(result)
            print(
                json.dumps({k: v for k, v in result.items() if k not in {"console"}}),
                flush=True,
            )
            context.close()
        browser.close()
    (ROOT / "logs/auth-min-alpha-browser.json").write_text(
        json.dumps(results, indent=2)
    )
    assert all(r["passed"] for r in results), "An alpha auth-flow case failed"


if __name__ == "__main__":
    main()
