"""Repeat the retained protected-async-var reload case with browser diagnostics."""

import importlib.util
import json
import sys
import traceback
from pathlib import Path

import reflex  # ENT_AUTH_VENV_GUARD

assert "/scratchpad/envs/ent_auth2-drv/" in reflex.__file__, reflex.__file__
from types import SimpleNamespace

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent


def load_tests():
    """Load only the retained upstream sample and browser test definitions.

    Returns:
        The upstream auth-flow module.
    """
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
    return sys.modules["upstream_auth_tests"]


def observe_frame(payload) -> dict:
    """Keep event/delta names and harmless fixture fields without token values.

    Args:
        payload: WebSocket text payload.

    Returns:
        Selected protocol diagnostics.
    """
    try:
        value = json.loads(payload)
    except (TypeError, ValueError):
        return {"non_json_frame": True}
    if not isinstance(value, dict):
        return {"non_object_frame": True}
    result = {"keys": sorted(value)}
    if "delta" in value:
        result["delta_states"] = list(value["delta"])
        result["fixture_delta"] = {
            name: {
                key: item
                for key, item in fields.items()
                if key
                in {
                    "secret",
                    "secret_view",
                    "admin_view",
                    "async_admin_view",
                    "public_count",
                }
            }
            for name, fields in value["delta"].items()
            if isinstance(fields, dict) and "flow_state" in name
        }
    if "name" in value:
        result["event_name"] = value["name"]
    return result


def main() -> None:
    """Run three fresh contexts and distinguish failure from delayed delivery."""
    tests = load_tests()
    harness = SimpleNamespace(frontend_url="http://localhost:3622/")
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path="/opt/pw-browsers/chromium")
        for attempt in range(1, 4):
            context = browser.new_context()
            page = context.new_page()
            record = {
                "attempt": attempt,
                "http": [],
                "failed_requests": [],
                "page_errors": [],
                "frames": [],
            }
            page.on(
                "response",
                lambda response, target=record: target["http"].append(
                    {"url": response.url.split("?")[0], "status": response.status}
                ),
            )
            page.on(
                "requestfailed",
                lambda request, target=record: target["failed_requests"].append(
                    {"url": request.url.split("?")[0], "failure": request.failure}
                ),
            )
            page.on(
                "pageerror",
                lambda error, target=record: target["page_errors"].append(str(error)),
            )
            page.on(
                "websocket",
                lambda socket, target=record: socket.on(
                    "framereceived",
                    lambda payload: target["frames"].append(observe_frame(payload)),
                ),
            )
            try:
                tests.test_protected_vars_survive_reload_on_public_page(harness, page)
                page.reload()
                expect(page.locator("#secret-view")).to_have_text(
                    "computed:initial-secret"
                )
                expect(page.locator("#async-admin-view")).to_have_text(
                    "async-admin-data"
                )
                record["successive_reloads"] = 2
                record["passed"] = True
            except Exception:
                record["passed"] = False
                record["traceback"] = traceback.format_exc()
                try:
                    expect(page.locator("#async-admin-view")).to_have_text(
                        "async-admin-data", timeout=15000
                    )
                    record["delivered_after_extra_wait"] = True
                except AssertionError:
                    record["delivered_after_extra_wait"] = False
            record["final_values"] = {
                name: page.locator("#" + name).inner_text()
                for name in ("secret", "secret-view", "admin-view", "async-admin-view")
            }
            page.screenshot(
                path=str(ROOT / "screenshots" / f"reload-repeat-{attempt}.png")
            )
            results.append(record)
            print(
                json.dumps(
                    {
                        key: record[key]
                        for key in (
                            "attempt",
                            "passed",
                            "delivered_after_extra_wait",
                            "final_values",
                        )
                        if key in record
                    }
                ),
                flush=True,
            )
            (ROOT / "logs/reload-repeat.json").write_text(
                json.dumps(results, indent=2) + "\n"
            )
            context.close()
        browser.close()


if __name__ == "__main__":
    main()
