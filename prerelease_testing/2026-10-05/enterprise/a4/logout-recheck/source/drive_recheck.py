"""Recheck normal account changes following application logout cleanup faults."""

import json
import re
import traceback
from datetime import datetime, timezone

from playwright.sync_api import expect, sync_playwright
from retained_driver import BASE, ROOT, action_records, cookie_summary, login, snapshot


def save(results: list[dict]) -> None:
    """Persist partial completion without raw authentication credentials.

    Args:
        results: Completed browser observations.
    """
    (ROOT / "logs/recheck.json").write_text(json.dumps(results, indent=2) + "\n")


def main() -> None:
    """Measure the same cleanup fault cases without manually clearing cookies."""
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for mode in ("normal", "frontend", "backend"):
                for name in ("frontend-unavailable", "backend-unavailable"):
                    (ROOT / name).unlink(missing_ok=True)
                context = browser.new_context()
                page = context.new_page()
                page.set_default_timeout(15_000)
                result = {
                    "case": mode,
                    "started_at_utc": datetime.now(timezone.utc).isoformat(),
                    "browser_version": browser.version,
                    "browser_cookies_manually_cleared": False,
                    "completed": False,
                    "console": [],
                    "page_errors": [],
                    "http_errors": [],
                    "failed_requests": [],
                }
                page.on(
                    "console",
                    lambda msg, record=result: record["console"].append(
                        {"type": msg.type, "text": msg.text}
                    ),
                )
                page.on(
                    "pageerror",
                    lambda err, record=result: record["page_errors"].append(str(err)),
                )
                page.on(
                    "response",
                    lambda response, record=result: (
                        record["http_errors"].append(
                            {
                                "url": response.url.split("?")[0],
                                "status": response.status,
                            }
                        )
                        if response.status >= 400
                        else None
                    ),
                )
                page.on(
                    "requestfailed",
                    lambda request, record=result: record["failed_requests"].append(
                        {"url": request.url.split("?")[0], "failure": request.failure}
                    ),
                )
                try:
                    page.goto(BASE + "/profile")
                    login(page, "alice")
                    page.get_by_role(
                        "button", name="Prime private data", exact=True
                    ).click()
                    expect(page.locator("#private-record")).to_contain_text(
                        "alice-PRIVATE-RECORD"
                    )
                    expect(page.locator("#private-cache")).to_have_text(
                        "alice-PRIVATE-CACHE"
                    )
                    result["before_logout"] = snapshot(page)
                    before = len(action_records())
                    if mode != "normal":
                        page.get_by_role(
                            "button", name=f"Arm {mode} outage", exact=True
                        ).click()
                        expect(page.locator("#armed")).to_have_text(mode)
                    page.get_by_role("button", name="Logout", exact=True).click()
                    if mode == "normal":
                        page.wait_for_url(re.compile("/oauth2/end_session"))
                        page.get_by_role(
                            "button", name="End session", exact=True
                        ).click()
                        page.wait_for_url(lambda url: url.split("?")[0] == BASE + "/")
                        result["logout_error"] = False
                    else:
                        expect(
                            page.get_by_text("Logout error", exact=True)
                        ).to_be_visible()
                        result["logout_error"] = True
                    result["after_logout"] = snapshot(page)
                    result["cookies_after_logout"] = cookie_summary(context)
                    page.get_by_role(
                        "button", name="Protected action", exact=True
                    ).click()
                    page.wait_for_url(re.compile("/login"))
                    result["post_logout_mutations"] = action_records()[before:]
                    result["redirected_to_login"] = True
                    for name in ("frontend-unavailable", "backend-unavailable"):
                        (ROOT / name).unlink(missing_ok=True)
                    result["application_dependency_recovered_before_login"] = True
                    login(page, "bob")
                    page.reload(wait_until="networkidle")
                    expect(page.locator("#identity")).to_have_text("bob")
                    result["after_account_change"] = snapshot(page)
                    body = page.inner_text("body")
                    result["previous_record_visible"] = "alice-PRIVATE-RECORD" in body
                    result["previous_cache_visible"] = "alice-PRIVATE-CACHE" in body
                    result["same_client_token"] = (
                        result["before_logout"]["token_fingerprint"]
                        == result["after_account_change"]["token_fingerprint"]
                    )
                    result["completed"] = True
                except Exception:
                    result["failure"] = traceback.format_exc()
                    result["last_snapshot"] = snapshot(page)
                finally:
                    results.append(result)
                    save(results)
                    try:
                        page.screenshot(
                            path=str(ROOT / f"screenshots/{mode}.png"), full_page=True
                        )
                    except Exception as error:
                        result["screenshot_error"] = str(error)
                        save(results)
                    print(
                        json.dumps(
                            {
                                key: result.get(key)
                                for key in (
                                    "case",
                                    "completed",
                                    "logout_error",
                                    "previous_record_visible",
                                    "previous_cache_visible",
                                    "same_client_token",
                                    "failure",
                                )
                            }
                        ),
                        flush=True,
                    )
                    context.close()
        finally:
            browser.close()
    assert all(result["completed"] for result in results), (
        "Browser recheck was incomplete"
    )


if __name__ == "__main__":
    main()
