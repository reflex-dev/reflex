"""Drive upstream AG Grid regressions and unchanged map demos in Chromium."""

import importlib.util
import json
import os
import re
import traceback
from pathlib import Path
from types import SimpleNamespace

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent
OUTPUT = Path(os.environ["QA_OUTPUT"])


def main() -> None:
    """Run the upstream tests and capture failures, console and network evidence."""
    spec = importlib.util.spec_from_file_location(
        "upstream_grid_tests",
        ROOT / "reference/tests__integration__ag_grid_app__test_ag_grid.py",
    )
    assert spec and spec.loader
    tests = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tests)
    app = SimpleNamespace(url=os.environ.get("QA_FRONTEND", "http://localhost:3131"))
    (OUTPUT / "logs").mkdir(parents=True, exist_ok=True)
    (OUTPUT / "screenshots").mkdir(parents=True, exist_ok=True)
    results = []
    cases = [
        (
            "sort_filter_pagination_pinned",
            lambda p: tests.test_render_sort_filter_and_paginate(p),
            "/",
        ),
        (
            "edit_row_id_backend_update",
            lambda p: tests.test_edit_event_and_state_update(p),
            "/",
        ),
        (
            "selection_helpers",
            lambda p: tests.test_selection_events_and_python_api(p),
            "/",
        ),
        ("loading_overlay", lambda p: tests.test_loading_overlay_api(p), "/"),
        ("csv_export", lambda p: tests.test_csv_export(p), "/"),
        ("grouping", lambda p: tests.test_enterprise_grouping(app, p), None),
        ("integrated_charts", lambda p: tests.test_integrated_chart(app, p), None),
    ]
    cases.extend(
        (f"theme_{theme}", lambda p, t=theme: tests.test_legacy_themes(p, t), "/")
        for theme in ["quartz", "alpine", "balham", "material"]
    )
    cases.extend(
        (
            f"overlay_suppressed_{suppressed}",
            lambda p, s=suppressed: tests.test_no_matching_rows_overlay(app, p, s),
            None,
        )
        for suppressed in [False, True]
    )
    cases.extend(
        (
            f"datasource_{route}",
            lambda p, r=route: tests.test_remote_datasources(app, p, r),
            None,
        )
        for route in ["infinite", "server-side"]
    )
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        for name, action, route in cases:
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()
            console = []
            failed_requests = []
            http_errors = []
            errors = []
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
            page.on("pageerror", lambda err, target=errors: target.append(str(err)))
            page.on(
                "requestfailed",
                lambda req, target=failed_requests: target.append(
                    {
                        "url": req.url,
                        "error": req.failure,
                    }
                ),
            )
            page.on(
                "response",
                lambda response, target=http_errors: (
                    target.append({"url": response.url, "status": response.status})
                    if response.status >= 400
                    else None
                ),
            )
            try:
                if route:
                    page.goto(app.url + route)
                    expect(page.locator("#ready")).to_have_text("true", timeout=45_000)
                    expect(tests.cell(page, 0, "name")).to_have_text("Alpha")
                action(page)
                assert not errors, errors
                configuration_errors = [
                    item["text"]
                    for item in console
                    if item["type"] in {"error", "warning"}
                    and re.search(r"AG (Grid|Charts):", item["text"])
                ]
                assert not configuration_errors, configuration_errors
                assert not http_errors, http_errors
                if name == "integrated_charts":
                    page.screenshot(
                        path=str(OUTPUT / "screenshots/ag-grid-integrated-chart.png"),
                        full_page=True,
                    )
                result = {"case": name, "passed": True}
            except Exception:
                result = {
                    "case": name,
                    "passed": False,
                    "traceback": traceback.format_exc(),
                }
                page.screenshot(
                    path=str(OUTPUT / "screenshots" / f"{name}-failure.png"),
                    full_page=True,
                )
            result.update(
                console=console,
                failed_requests=failed_requests,
                page_errors=errors,
                http_errors=http_errors,
            )
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
    (OUTPUT / "logs/components-browser.json").write_text(json.dumps(results, indent=2))
    assert all(r["passed"] for r in results), "One or more browser cases failed"


if __name__ == "__main__":
    main()
