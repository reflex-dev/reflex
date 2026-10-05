"""Inspect portal-based chart ticks and editor/media browser targets."""

import json
import sys

from playwright.sync_api import expect, sync_playwright


def main() -> None:
    """Print the relevant live DOM without importing the app source."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        page.goto(sys.argv[1])
        if len(sys.argv) < 3:
            expect(page.locator("#token")).not_to_have_text("")
        expect(page.locator("#recharts-panel svg")).to_be_visible()
        print(  # noqa: T201
            json.dumps(
                page.evaluate("""() => ({
            chartText: document.querySelector('#recharts-panel').textContent,
            axis: document.querySelector('#recharts-panel .recharts-yAxis').outerHTML,
            media: [...document.querySelectorAll('audio,video')].map(el => el.outerHTML),
            editor: document.querySelector('#dataeditor-panel').outerHTML,
            shiki: document.querySelector('#shiki-in-form').outerHTML,
        })"""),
                indent=2,
            )
        )
        browser.close()


if __name__ == "__main__":
    main()
