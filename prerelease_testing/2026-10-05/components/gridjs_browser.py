"""Record Grid.js console behavior before and after a mutable table update."""

import importlib.metadata
import json
import sys
from pathlib import Path

import reflex
from playwright.sync_api import expect, sync_playwright


def main() -> None:
    """Run the same table filter and state update for each published graph."""
    url, output_name = sys.argv[1:]
    result = {
        "versions": {
            name: importlib.metadata.version(name)
            for name in ("reflex", "reflex-base", "reflex-components-gridjs")
        },
        "reflex": reflex.__file__,
        "console": [],
        "page_errors": [],
        "stage": "initial",
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        page.on(
            "console",
            lambda item: result["console"].append({
                "stage": result["stage"],
                "type": item.type,
                "text": item.text,
            }),
        )
        page.on("pageerror", lambda item: result["page_errors"].append(str(item)))
        page.goto(url)
        expect(page.locator("#token")).not_to_have_text("", timeout=30000)
        expect(page.locator(".gridjs-tbody")).to_contain_text("Alpha")
        result["stage"] = "search"
        page.locator("input.gridjs-search-input").fill("Beta")
        expect(page.locator(".gridjs-tbody")).to_contain_text("Beta")
        expect(page.locator(".gridjs-tbody")).not_to_contain_text("Alpha")
        result["stage"] = "update"
        page.get_by_role("button", name="Edit first product").click()
        expect(page.locator("#first-product")).to_have_text("Gamma")
        result["stage"] = "clear-search"
        page.locator("input.gridjs-search-input").fill("")
        expect(page.locator(".gridjs-tbody")).to_contain_text("Gamma")
        result["table"] = page.locator(".gridjs-tbody").text_content()
        browser.close()
    Path(output_name).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result), flush=True)  # noqa: T201


if __name__ == "__main__":
    main()
