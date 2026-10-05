"""Capture the actual many-State client failure after a fresh Bun install."""

import argparse
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    """Retain blank-page, console and screenshot evidence without hiding errors."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    result = {"url": args.url, "console": [], "page_errors": [], "network": []}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get("QA_CHROME_EXECUTABLE")
        )
        page = browser.new_page()
        page.on(
            "console",
            lambda message: result["console"].append(
                {"type": message.type, "text": message.text}
            ),
        )
        page.on("pageerror", lambda error: result["page_errors"].append(str(error)))
        page.on(
            "response",
            lambda response: result["network"].append(
                {"url": response.url, "status": response.status}
            ),
        )
        page.goto(args.url, wait_until="networkidle")
        page.screenshot(path=str(args.output / "blank-page.png"), full_page=True)
        result["body"] = page.locator("body").inner_text()
        result["browser_version"] = browser.version
        errors = result["page_errors"] + [
            message["text"]
            for message in result["console"]
            if message["type"] == "error"
        ]
        result["stack_overflow_observed"] = any(
            "Maximum call stack size exceeded" in error for error in errors
        )
        (args.output / "browser.json").write_text(json.dumps(result, indent=2) + "\n")
        browser.close()
    assert result["stack_overflow_observed"], result
    assert "Article 7" not in result["body"], result["body"]


if __name__ == "__main__":
    main()
