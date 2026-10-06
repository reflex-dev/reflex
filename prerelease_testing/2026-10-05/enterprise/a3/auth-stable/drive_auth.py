"""Run upstream auth-flow cases against the live isolated sample app."""

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


def main() -> None:
    """Drive the upstream auth cases with isolated browser sessions."""
    for name, filename in [
        ("auth_harness", "tests__integration__auth_harness.py"),
        ("upstream_auth_tests", "tests__integration__test_auth_flow.py"),
    ]:
        spec = importlib.util.spec_from_file_location(
            name, ROOT / "reference" / filename
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    tests = sys.modules["upstream_auth_tests"]
    harness = SimpleNamespace(frontend_url="http://localhost:3152/")
    cases = [
        name
        for name in vars(tests)
        if name.startswith("test_") and not name.startswith("test_custom_")
    ]
    assert len(cases) == 22, cases
    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        browser_version = browser.version
        for name in cases:
            context = browser.new_context()
            page = context.new_page()
            page.set_default_timeout(15_000)
            console, errors, failures, responses = [], [], [], []
            page.on(
                "console",
                lambda msg, target=console: target.append(
                    {
                        "type": msg.type,
                        "text": msg.text,
                        "location": msg.location,
                    }
                ),
            )
            page.on("pageerror", lambda error, target=errors: target.append(str(error)))
            page.on(
                "requestfailed",
                lambda req, target=failures: target.append(
                    {
                        "url": req.url.split("?")[0],
                        "failure": req.failure,
                    }
                ),
            )
            page.on(
                "response",
                lambda response, target=responses: target.append(
                    {
                        "url": response.url.split("?")[0],
                        "status": response.status,
                    }
                ),
            )
            try:
                getattr(tests, name)(harness, page)
                assert not errors, errors
                result = {"case": name, "passed": True}
            except Exception:
                LOGGER.exception("Auth browser case %s failed", name)
                result = {
                    "case": name,
                    "passed": False,
                    "traceback": traceback.format_exc(),
                }
                page.screenshot(
                    path=str(ROOT / "screenshots" / f"stable-{name}-failure.png"),
                    full_page=True,
                )
            result.update(console=console, page_errors=errors, failed_requests=failures)
            result["responses"] = responses
            result["browser_version"] = browser_version
            result["last_url"] = page.url.split("?")[0]
            result["cookies"] = [
                {key: value for key, value in cookie.items() if key != "value"}
                | {"value_length": len(cookie["value"])}
                for cookie in context.cookies()
            ]
            result["visible_fields"] = {}
            for selector in (
                "#secret",
                "#secret-view",
                "#count",
                "#public-view",
                "#admin-view",
                "#async-admin-view",
                "#async-log",
                "#refresh-result",
                "#user-name",
                "#user-email",
            ):
                locator = page.locator(selector)
                if locator.count():
                    result["visible_fields"][selector] = locator.first.inner_text()
            results.append(result)
            (ROOT / "logs/auth-stable-browser.json").write_text(
                json.dumps(results, indent=2)
            )
            print(
                json.dumps(
                    {
                        k: v
                        for k, v in result.items()
                        if k in {"case", "passed", "traceback"}
                    }
                ),
                flush=True,
            )
            context.close()
        browser.close()
    (ROOT / "logs/auth-stable-browser.json").write_text(json.dumps(results, indent=2))
    assert all(r["passed"] for r in results), "Some upstream auth-flow cases failed"


if __name__ == "__main__":
    main()
