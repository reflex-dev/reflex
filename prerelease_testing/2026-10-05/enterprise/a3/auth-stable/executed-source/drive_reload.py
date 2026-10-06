"""Observe protected async vars across login and a public full-page reload."""

import json
import re
import sys
import time
import traceback
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

ROOT = Path(__file__).resolve().parent
FRONTEND = "http://localhost:3152"
SELECTORS = ("#secret", "#sync-view", "#async-view", "#user-name")


def fields(page: Page) -> dict[str, str]:
    """Read the visible probe fields.

    Args:
        page: The current browser page.

    Returns:
        Values of the markers present in the document.
    """
    return {
        selector: page.locator(selector).inner_text()
        for selector in SELECTORS
        if page.locator(selector).count()
    }


def console_record(message) -> dict:
    """Capture console metadata without OIDC query parameters.

    Args:
        message: The Playwright console message.

    Returns:
        A diagnostic entry with a sanitized source URL.
    """
    location = dict(message.location)
    location["url"] = location.get("url", "").split("?")[0]
    return {"type": message.type, "text": message.text, "location": location}


def main() -> None:
    """Run three isolated login/reload observations and preserve partial data."""
    label = sys.argv[1] if len(sys.argv) > 1 else "alpha"
    (ROOT / "logs").mkdir(exist_ok=True)
    (ROOT / "screenshots").mkdir(exist_ok=True)
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for repeat in range(3):
            context = browser.new_context()
            page = context.new_page()
            page.set_default_timeout(15000)
            result = {
                "repeat": repeat + 1,
                "browser_version": browser.version,
                "console": [],
                "page_errors": [],
                "http_errors": [],
            }
            page.on("console", lambda message, target=result: target["console"].append(console_record(message)))
            page.on("pageerror", lambda error, target=result: target["page_errors"].append(str(error)))
            page.on("response", lambda response, target=result: target["http_errors"].append({"url": response.url.split("?")[0], "status": response.status}) if response.status >= 400 else None)
            try:
                page.goto(FRONTEND + "/dashboard")
                page.get_by_role("button", name="Login with Generic").click()
                page.wait_for_url(re.compile(r"/oauth2/authorize"))
                page.locator('button[name="sub"][value="alice"]').click()
                page.wait_for_url(re.compile(r"localhost:3152/(?!callback|login)"))
                if not page.url.startswith(FRONTEND + "/dashboard"):
                    page.goto(FRONTEND + "/dashboard")
                expect(page.locator("#async-view")).to_have_text("async-admin-data")
                result["authenticated_dashboard"] = fields(page)
                page.goto(FRONTEND + "/")
                expect(page.locator("#sync-view")).to_have_text("computed:initial-secret")
                page.wait_for_timeout(1000)
                result["before_reload"] = fields(page)
                page.reload()
                expect(page.locator("#sync-view")).to_have_text("computed:initial-secret")
                started = time.monotonic()
                observations = []
                for seconds in (0, 1, 5, 15):
                    page.wait_for_timeout(max(0, seconds - (time.monotonic() - started)) * 1000)
                    observations.append({"elapsed_seconds": round(time.monotonic() - started, 3), "fields": fields(page)})
                result["after_reload"] = observations
                result["async_restored"] = observations[-1]["fields"].get("#async-view") == "async-admin-data"
                result["completed"] = True
            except Exception:
                result["completed"] = False
                result["traceback"] = traceback.format_exc()
            result["cookies"] = [{key: value for key, value in cookie.items() if key != "value"} | {"value_length": len(cookie["value"])} for cookie in context.cookies()]
            page.screenshot(path=str(ROOT / "screenshots" / f"{label}-{repeat + 1}.png"), full_page=True)
            results.append(result)
            (ROOT / "logs" / f"reload-{label}.json").write_text(json.dumps(results, indent=2))
            print(json.dumps({key: value for key, value in result.items() if key in {"repeat", "completed", "before_reload", "after_reload", "async_restored", "traceback"}}), flush=True)
            context.close()
        browser.close()
    assert all(result["completed"] for result in results), "The setup or browser observations failed"


if __name__ == "__main__":
    main()
