"""Run upstream auth-flow cases against the live isolated sample app."""

import importlib.util
import json
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent


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
    harness = SimpleNamespace(frontend_url="http://localhost:3132/")
    cases = [
        name
        for name in vars(tests)
        if name.startswith("test_") and not name.startswith("test_custom_")
    ]
    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        for name in cases:
            context = browser.new_context()
            page = context.new_page()
            page.set_default_timeout(15_000)
            console, errors, failures = [], [], []
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
                lambda req, target=failures: target.append(
                    {
                        "url": req.url.split("?")[0],
                        "failure": req.failure,
                    }
                ),
            )
            try:
                getattr(tests, name)(harness, page)
                assert not errors, errors
                result = {"case": name, "passed": True}
            except Exception:
                result = {
                    "case": name,
                    "passed": False,
                    "traceback": traceback.format_exc(),
                }
                page.screenshot(
                    path=str(ROOT / "screenshots" / f"full-{name}-failure.png"),
                    full_page=True,
                )
            result.update(console=console, page_errors=errors, failed_requests=failures)
            results.append(result)
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
    (ROOT / "logs/auth-full-browser.json").write_text(json.dumps(results, indent=2))
    assert all(r["passed"] for r in results), "Some upstream auth-flow cases failed"


if __name__ == "__main__":
    main()
