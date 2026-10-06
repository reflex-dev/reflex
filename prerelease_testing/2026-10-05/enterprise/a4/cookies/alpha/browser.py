"""Validate fictional HTTP-only cookies through a real browser and backend."""

import argparse
import json
import time
import traceback
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright


def wait_cookies(context, expected: dict[str, str | None]) -> list[dict]:
    """Wait for the browser cookie jar to contain the expected synthetic values.

    Args:
        context: Browser context owning the cookie jar.
        expected: Fictional cookie names and expected values, or None for deletion.

    Returns:
        The two test-cookie records.

    Raises:
        AssertionError: If the expected cookie values do not arrive.
    """
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        cookies = [
            c for c in context.cookies() if c["name"] in {"qa_first", "qa_second"}
        ]
        values = {cookie["name"]: cookie["value"] for cookie in cookies}
        if all(values.get(name) == value for name, value in expected.items()):
            return cookies
        context.pages[0].wait_for_timeout(100)
    raise AssertionError({"expected": expected, "cookies": cookies})


def main() -> None:
    """Run cookie scenarios and save partial evidence even on a failed assertion."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:3145")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    diagnostics = {
        "console": [],
        "page_errors": [],
        "http_errors": [],
        "failed_requests": [],
        "cookie_sync": [],
    }
    results = []
    failure = None
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(15_000)
        page.on(
            "console",
            lambda message: diagnostics["console"].append({
                "type": message.type,
                "text": message.text,
                "location": message.location,
            }),
        )
        page.on(
            "pageerror", lambda error: diagnostics["page_errors"].append(str(error))
        )
        page.on(
            "requestfailed",
            lambda request: diagnostics["failed_requests"].append({
                "url": request.url,
                "failure": request.failure,
            }),
        )

        def response_received(response) -> None:
            """Record HTTP failures and actual cookie synchronization headers.

            Args:
                response: Real browser HTTP response.
            """
            if response.status >= 400:
                diagnostics["http_errors"].append({
                    "url": response.url,
                    "status": response.status,
                })
            if urlsplit(response.url).path == "/_reflex/cookies/sync":
                diagnostics["cookie_sync"].append({
                    "status": response.status,
                    "set_cookie": response.header_values("set-cookie"),
                })

        page.on("response", response_received)
        try:
            page.goto(args.base_url, wait_until="networkidle")
            expect(page.get_by_role("heading", name="HTTP cookie QA")).to_be_visible()
            expect(page.locator("#first")).to_have_text("")
            expect(page.locator("#inherited")).to_have_text("child:")
            results.append({"scenario": "initial_defaults", "passed": True})

            page.get_by_role("button", name="Set pair", exact=True).click()
            expect(page.locator("#first")).to_have_text("first-1")
            expect(page.locator("#second")).to_have_text("second-1")
            expect(page.locator("#inherited")).to_have_text("child:first-1")
            cookies = wait_cookies(
                context, {"qa_first": "first-1", "qa_second": "second-1"}
            )
            assert all(cookie["httpOnly"] for cookie in cookies), cookies
            assert "qa_first=" not in page.evaluate("document.cookie")
            assert "qa_second=" not in page.evaluate("document.cookie")
            results.append({
                "scenario": "backend_pair_http_only_inherited_memo",
                "passed": True,
                "cookies": cookies,
            })

            for _ in range(5):
                page.get_by_role("button", name="Set pair", exact=True).click()
            expect(page.locator("#first")).to_have_text("first-6")
            expect(page.locator("#second")).to_have_text("second-6")
            expect(page.locator("#inherited")).to_have_text("child:first-6")
            cookies = wait_cookies(
                context, {"qa_first": "first-6", "qa_second": "second-6"}
            )
            results.append({
                "scenario": "paired_burst_without_clobber",
                "passed": True,
                "cookies": cookies,
            })

            page.reload(wait_until="networkidle")
            expect(page.locator("#first")).to_have_text("first-6")
            expect(page.locator("#second")).to_have_text("second-6")
            expect(page.locator("#inherited")).to_have_text("child:first-6")
            results.append({"scenario": "reload_persistence", "passed": True})

            context.add_cookies([
                {
                    "name": "qa_first",
                    "value": "browser-first",
                    "url": args.base_url,
                    "httpOnly": True,
                },
                {
                    "name": "qa_second",
                    "value": "browser-second",
                    "url": args.base_url,
                    "httpOnly": True,
                },
            ])
            page.get_by_role("button", name="Sync browser", exact=True).click()
            expect(page.locator("#reads")).to_have_text("1")
            expect(page.locator("#first")).to_have_text("browser-first")
            expect(page.locator("#second")).to_have_text("browser-second")
            expect(page.locator("#inherited")).to_have_text("child:browser-first")
            results.append({
                "scenario": "browser_to_backend_dependency_invalidation",
                "passed": True,
            })

            page.get_by_role("button", name="Delete pair", exact=True).click()
            expect(page.locator("#first")).to_have_text("")
            expect(page.locator("#second")).to_have_text("")
            expect(page.locator("#inherited")).to_have_text("child:")
            wait_cookies(context, {"qa_first": None, "qa_second": None})
            results.append({"scenario": "explicit_delete", "passed": True})

            assert diagnostics["cookie_sync"] and all(
                item["status"] == 200 for item in diagnostics["cookie_sync"]
            ), diagnostics
            assert not diagnostics["page_errors"], diagnostics
            unexpected_http = [
                item
                for item in diagnostics["http_errors"]
                if urlsplit(item["url"]).path != "/favicon.ico"
            ]
            assert not unexpected_http, unexpected_http
            unexpected_console = [
                item
                for item in diagnostics["console"]
                if item["type"] == "error"
                and "favicon.ico" not in item["location"].get("url", "")
            ]
            assert not unexpected_console, unexpected_console
        except Exception:
            failure = traceback.format_exc()
        finally:
            page.screenshot(path=str(args.output / "browser.png"), full_page=True)
            result = {
                "passed": failure is None,
                "scenarios": results,
                "failure": failure,
                "diagnostics": diagnostics,
                "body": page.locator("body").inner_text(),
                "browser_version": browser.version,
            }
            (args.output / "browser.json").write_text(
                json.dumps(result, indent=2) + "\n"
            )
            print(
                json.dumps({
                    "passed": result["passed"],
                    "scenario_count": len(results),
                    "failure": failure,
                }),
                flush=True,
            )
            context.close()
            browser.close()
    raise SystemExit(failure is not None)


if __name__ == "__main__":
    main()
