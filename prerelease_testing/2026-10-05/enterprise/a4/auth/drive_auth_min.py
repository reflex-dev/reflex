"""Drive default AuthPlugin and normalized profile vars on the alpha."""

import json
import os
import re
import traceback
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent
BASE = "http://localhost:3132"
MODE = "extra" if os.environ.get("AUTH_TEST_EXTRA_SCOPES") else "default"


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
            "iframe_pending_event_replay",
        ]:
            context = browser.new_context()
            page = context.new_page()
            page.set_default_timeout(20_000)
            console, errors, failures, responses = [], [], [], []
            page.on(
                "console",
                lambda msg, target=console: target.append(
                    {
                        "type": msg.type,
                        "text": msg.text,
                    }
                ),
            )
            page.on("pageerror", lambda error, target=errors: target.append(str(error)))
            page.on(
                "requestfailed",
                lambda request, target=failures: target.append(
                    {
                        "url": request.url.split("?")[0],
                        "failure": request.failure,
                    }
                ),
            )
            page.on(
                "response",
                lambda response, target=responses: (
                    target.append(
                        {
                            "url": response.url.split("?")[0],
                            "status": response.status,
                        }
                    )
                    if response.status >= 400
                    else None
                ),
            )
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
                    page.get_by_role("button", name="Refresh", exact=True).click()
                    expect(page.locator("#refresh-result")).to_have_text("refreshed")
                    page.screenshot(
                        path=str(ROOT / "screenshots" / f"auth-min-{MODE}-profile.png")
                    )
                    page.get_by_role("button", name="Logout", exact=True).click()
                    page.wait_for_url(re.compile("/oauth2/end_session"))
                    page.get_by_role("button", name="End session", exact=True).click()
                    page.wait_for_url(lambda url: url.split("?")[0] == BASE + "/")
                    expect(page.get_by_text("Logout error", exact=True)).to_have_count(
                        0
                    )
                    expect(
                        page.get_by_role("button", name="Login with Generic")
                    ).to_be_visible()
                    expect(page.locator("#message")).to_have_text("initial")
                    page.screenshot(
                        path=str(
                            ROOT / "screenshots" / f"auth-min-{MODE}-logged-out.png"
                        )
                    )
                    page.goto(BASE + "/profile")
                    page.wait_for_url(re.compile("/login"))
                    authorize(page, "bob")
                    page.wait_for_url(BASE + "/profile")
                    expect(page.locator("#name")).to_have_text("Bob Member")
                    expect(page.locator("#email")).to_have_text("bob@example.com")
                    expect(page.locator("#message")).to_have_text("initial")
                    page.get_by_role("button", name="Reveal", exact=True).click()
                    expect(page.locator("#message")).to_have_text("revealed-bob")
                    assert "Alice Admin" not in page.inner_text("body")
                    page.screenshot(
                        path=str(ROOT / "screenshots" / f"auth-min-{MODE}-bob.png")
                    )
                elif case == "anonymous_event_replay":
                    page.goto(BASE)
                    page.get_by_role("button", name="Reveal", exact=True).click()
                    page.wait_for_url(re.compile("/login"))
                    authorize(page)
                    page.wait_for_url(lambda url: url.split("?")[0] == BASE + "/")
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
                elif case == "iframe_pending_event_replay":
                    page.goto(BASE + "/iframe")
                    frame = page.frame_locator("iframe")
                    frame.get_by_role("button", name="Reveal", exact=True).click()
                    with page.expect_popup() as opened:
                        frame.get_by_role(
                            "button", name="Login with Generic", exact=True
                        ).click()
                    popup = opened.value
                    popup.wait_for_url(re.compile("/oauth2/authorize"))
                    popup.locator('button[name="sub"][value="alice"]').click()
                    popup.wait_for_event("close")
                    expect(frame.locator("#message")).to_have_text("revealed-alice")
                    child = next(item for item in page.frames if item.parent_frame)
                    assert not child.evaluate(
                        "sessionStorage.getItem('rxe_auth_pending_event')"
                    )
                    page.screenshot(
                        path=str(
                            ROOT / "screenshots" / f"auth-min-{MODE}-iframe-replay.png"
                        )
                    )
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
                    path=str(
                        ROOT / "screenshots" / f"auth-min-{MODE}-{case}-failure.png"
                    )
                )
            result.update(
                console=console,
                page_errors=errors,
                failed_requests=failures,
                http_errors=responses,
            )
            if case.startswith("iframe"):
                result["frame_observations"] = [
                    {
                        "url": child.url,
                        "text": child.locator("body").inner_text(),
                        "pending_event": child.evaluate(
                            "sessionStorage.getItem('rxe_auth_pending_event')"
                        ),
                    }
                    for child in page.frames
                    if child.parent_frame
                ]
            if case == "iframe_pending_event_replay" and not result["passed"]:
                child = next(item for item in page.frames if item.parent_frame)
                child.goto(BASE + "/")
                try:
                    expect(child.locator("#message")).to_have_text(
                        "revealed-alice", timeout=10000
                    )
                    result["direct_child_navigation_recovery"] = {
                        "replayed": True,
                        "pending_consumed": not child.evaluate(
                            "sessionStorage.getItem('rxe_auth_pending_event')"
                        ),
                    }
                except AssertionError:
                    result["direct_child_navigation_recovery"] = {"replayed": False}
            results.append(result)
            print(
                json.dumps({k: v for k, v in result.items() if k not in {"console"}}),
                flush=True,
            )
            context.close()
        browser.close()
    (ROOT / "logs" / f"auth-min-{MODE}-browser.json").write_text(
        json.dumps(results, indent=2)
    )
    assert all(r["passed"] for r in results), "An alpha auth-flow case failed"


if __name__ == "__main__":
    main()
