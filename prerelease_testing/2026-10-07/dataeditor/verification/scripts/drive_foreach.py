"""Drive the independent foreach reproduction and capture full error stacks."""

import argparse
import json
import os
from pathlib import Path

import playwright
from playwright.sync_api import sync_playwright

assert Path(playwright.__file__).is_relative_to(
    Path(os.environ["SB"]) / "envs" / "driver"
), playwright.__file__


def main() -> int:
    """Capture each scenario in a fresh browser context.

    Returns:
        Zero when all three scenarios render without JavaScript errors.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("base")
    parser.add_argument("output", type=Path)
    parser.add_argument("--browser", choices=["chromium", "webkit"], default="chromium")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = {}
    with sync_playwright() as pw:
        browser = getattr(pw, args.browser).launch()
        try:
            for name, path, expected in (("control", "/", 1), ("foreach", "/foreach", 2), ("memo", "/memo", 2)):
                record = {"console": [], "pageerrors": [], "requests_failed": [], "http_errors": [], "ws_frames": []}
                results[name] = record
                context = browser.new_context(viewport={"width": 1000, "height": 700})
                try:
                    page = context.new_page()
                    page.on("console", lambda message: record["console"].append({"type": message.type, "text": message.text, "location": message.location}))
                    page.on("pageerror", lambda error: record["pageerrors"].append({"name": error.name, "message": error.message, "stack": error.stack}))
                    page.on("requestfailed", lambda request: record["requests_failed"].append({"url": request.url, "failure": request.failure}))
                    page.on("response", lambda response: record["http_errors"].append({"url": response.url, "status": response.status}) if response.status >= 400 else None)
                    page.on("websocket", lambda ws: ws.on("framereceived", lambda frame: record["ws_frames"].append(str(frame)[:1500]) if len(record["ws_frames"]) < 10 else None))
                    page.goto(args.base.rstrip("/") + path, wait_until="networkidle")
                    page.wait_for_timeout(4000)
                    record["body"] = page.locator("body").inner_text()
                    record["grid_count"] = page.locator("canvas[data-testid='data-grid-canvas']").count()
                    record["browser"] = browser.version
                    record["user_agent"] = page.evaluate("navigator.userAgent")
                    record["pass"] = record["grid_count"] == expected and not record["pageerrors"] and not any(message["type"] == "error" for message in record["console"])
                    page.screenshot(path=str(args.output / f"{name}.png"), full_page=True)
                except Exception as error:
                    record["driver_error"] = repr(error)
                    record["pass"] = False
                finally:
                    context.close()
                (args.output / "results.json").write_text(json.dumps(results, indent=2))
                print(name, "PASS" if record["pass"] else "FAIL", record.get("grid_count"), flush=True)
        finally:
            browser.close()
    return 0 if all(record["pass"] for record in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
