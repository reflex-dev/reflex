"""Repeat the exact retained public-page protected async-var reload case."""

import importlib.util
import json
import logging
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
LOGGER = logging.getLogger(__name__)


def load_tests():
    """Import retained browser definitions without starting their AppHarness.

    Returns:
        The module containing the exact upstream browser case.
    """
    for name, filename in (
        ("auth_harness", "tests__integration__auth_harness.py"),
        ("upstream_auth_tests", "tests__integration__test_auth_flow.py"),
    ):
        spec = importlib.util.spec_from_file_location(
            name, ROOT / "reference" / filename
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules["upstream_auth_tests"]


def main() -> None:
    """Drive five fresh sessions and retain field/cookie/browser diagnostics."""
    tests = load_tests()
    harness = SimpleNamespace(frontend_url="http://localhost:3152/")
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for index in range(5):
            context = browser.new_context()
            page = context.new_page()
            page.set_default_timeout(15000)
            result = {
                "repeat": index + 1,
                "browser_version": browser.version,
                "console": [],
                "page_errors": [],
                "http_errors": [],
            }
            page.on(
                "console",
                lambda message, target=result: target["console"].append(
                    {
                        "type": message.type,
                        "text": message.text,
                        "location": message.location,
                    }
                ),
            )
            page.on(
                "pageerror",
                lambda error, target=result: target["page_errors"].append(str(error)),
            )
            page.on(
                "response",
                lambda response, target=result: (
                    target["http_errors"].append(
                        {"url": response.url.split("?")[0], "status": response.status}
                    )
                    if response.status >= 400
                    else None
                ),
            )
            try:
                tests.test_protected_vars_survive_reload_on_public_page(harness, page)
                result["passed"] = True
            except Exception:
                LOGGER.exception("Public-page reload repeat %s failed", index + 1)
                result["passed"] = False
                result["traceback"] = traceback.format_exc()
            result["visible_fields"] = {
                selector: page.locator(selector).inner_text()
                for selector in (
                    "#secret",
                    "#secret-view",
                    "#async-admin-view",
                    "#count",
                    "#admin-view",
                )
                if page.locator(selector).count()
            }
            result["cookies"] = [
                {key: value for key, value in cookie.items() if key != "value"}
                | {"value_length": len(cookie["value"])}
                for cookie in context.cookies()
            ]
            page.screenshot(
                path=str(ROOT / "screenshots" / f"focused-reload-{index + 1}.png"),
                full_page=True,
            )
            results.append(result)
            (ROOT / "logs/focused-reload.json").write_text(
                json.dumps(results, indent=2)
            )
            context.close()
        browser.close()
    assert all(result["passed"] for result in results), results
    print(
        json.dumps(
            {
                "repeats": len(results),
                "passed": sum(result["passed"] for result in results),
            }
        )
    )


if __name__ == "__main__":
    main()
