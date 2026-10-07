"""Capture deletion behavior with and without a backend on_delete event."""

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
    """Exercise the two pages with both macOS deletion key variants.

    Returns:
        Zero if all cases edit exactly one text cell without JavaScript errors.
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
            for name, route in (("control", "/"), ("bound", "/bound")):
                for key in ("Delete", "Backspace"):
                    record = {"console": [], "pageerrors": [], "requests_failed": [], "http_errors": []}
                    label = f"{name}-{key}"
                    results[label] = record
                    context = browser.new_context(viewport={"width": 1000, "height": 700})
                    try:
                        page = context.new_page()
                        page.on("console", lambda message: record["console"].append({"type": message.type, "text": message.text}))
                        page.on("pageerror", lambda error: record["pageerrors"].append({"message": error.message, "stack": error.stack}))
                        page.on("requestfailed", lambda request: record["requests_failed"].append({"url": request.url, "failure": request.failure}))
                        page.on("response", lambda response: record["http_errors"].append({"url": response.url, "status": response.status}) if response.status >= 400 else None)
                        page.goto(args.base.rstrip("/") + route, wait_until="networkidle")
                        canvas = page.locator("#grid canvas[data-testid='data-grid-canvas']")
                        canvas.wait_for(state="visible")
                        page.wait_for_timeout(1500)
                        box = canvas.bounding_box()
                        page.mouse.click(box["x"] + 100, box["y"] + 56)
                        expect(page.locator("#clicked")).to_have_text("[0, 0]")
                        record["before"] = page.locator("#rows").inner_text()
                        page.keyboard.press(key)
                        page.wait_for_timeout(2000)
                        record["after"] = page.locator("#rows").inner_text()
                        record["edits"] = page.locator("#edits").inner_text()
                        record["deleted"] = page.locator("#deleted").inner_text()
                        record["versions"] = page.locator("#versions").inner_text()
                        record["browser"] = browser.version
                        record["pass"] = record["edits"] == "1" and json.loads(record["after"])[0][0] == "" and not record["pageerrors"]
                        page.screenshot(path=str(args.output / f"{label}.png"), full_page=True)
                    except Exception as error:
                        record["driver_error"] = repr(error)
                        record["pass"] = False
                    finally:
                        context.close()
                    (args.output / "results.json").write_text(json.dumps(results, indent=2))
                    print(label, "PASS" if record["pass"] else "FAIL", record.get("edits"), flush=True)
        finally:
            browser.close()
    return 0 if all(record["pass"] for record in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
