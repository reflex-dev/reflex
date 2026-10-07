"""Isolate Radix form-control click errors caused by a data editor on the page."""

import argparse
import json
import os
from pathlib import Path

import playwright
from playwright.sync_api import expect, sync_playwright

assert Path(playwright.__file__).is_relative_to(
    Path(os.environ["SB"]) / "envs" / "driver"
), playwright.__file__


def main() -> int:
    """Record click outcomes and exception stacks with and without the grid.

    Returns:
        Zero if both pages remain free of JavaScript errors.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("base")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            for name in ("form-only", "form-grid"):
                phase = "load"
                record = {"console": [], "pageerrors": [], "http_errors": [], "requests_failed": [], "clicks": []}
                results[name] = record
                context = browser.new_context(viewport={"width": 1000, "height": 700})
                try:
                    page = context.new_page()
                    page.add_init_script("window.__probeClicks=[];document.addEventListener('click', e => window.__probeClicks.push({type:e.constructor.name,target:e.target.tagName,id:e.target.id,checked:e.target.checked,mouse:e instanceof MouseEvent}),true)")
                    page.on("console", lambda message: record["console"].append({"phase": phase, "type": message.type, "text": message.text}))
                    page.on("pageerror", lambda error: record["pageerrors"].append({"phase": phase, "message": error.message, "stack": error.stack}))
                    page.on("response", lambda response: record["http_errors"].append({"url": response.url, "status": response.status}) if response.status >= 400 else None)
                    page.on("requestfailed", lambda request: record["requests_failed"].append({"url": request.url, "failure": request.failure}))
                    page.goto(args.base.rstrip("/") + "/" + name, wait_until="networkidle")
                    page.wait_for_timeout(1500)
                    for phase, selector in (("checkbox", "#checkbox"), ("switch", "#switch"), ("radio", "#radio button[value='b']")):
                        page.locator(selector).click()
                        expect(page.locator(selector)).to_have_attribute("aria-checked", "true")
                        page.wait_for_timeout(500)
                    record["clicks"] = page.evaluate("window.__probeClicks")
                    record["grid_count"] = page.locator("canvas[data-testid='data-grid-canvas']").count()
                    record["browser"] = browser.version
                    record["pass"] = not record["pageerrors"]
                    page.screenshot(path=str(args.output / f"{name}.png"), full_page=True)
                except Exception as error:
                    record["driver_error"] = repr(error)
                    record["pass"] = False
                finally:
                    context.close()
                (args.output / "results.json").write_text(json.dumps(results, indent=2))
                print(name, "PASS" if record["pass"] else "FAIL", len(record["pageerrors"]), flush=True)
        finally:
            browser.close()
    return 0 if all(record["pass"] for record in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
