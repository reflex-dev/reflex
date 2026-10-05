"""Drive runtime or Todo upgrade pages and retain transport diagnostics."""

import argparse
import json
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main() -> None:
    """Exercise actual browser interactions against an already running app."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--todo", action="store_true")
    parser.add_argument("--css-path", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    evidence = {
        "url": args.url,
        "console": [],
        "page_errors": [],
        "network": [],
        "checks": [],
    }
    original_css = args.css_path.read_text() if args.css_path else None
    with sync_playwright() as playwright:
        executable = os.environ.get("QA_CHROME_EXECUTABLE")
        browser = playwright.chromium.launch(executable_path=executable)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.on(
            "console",
            lambda message: evidence["console"].append(
                {"type": message.type, "text": message.text}
            ),
        )
        page.on("pageerror", lambda error: evidence["page_errors"].append(str(error)))
        page.on(
            "response",
            lambda response: evidence["network"].append(
                {"url": response.url, "status": response.status}
            ),
        )
        try:
            page.goto(args.url, wait_until="domcontentloaded")
            if args.todo:
                label = "QA browser upgrade #100% ✓"
                page.get_by_placeholder("Add a todo...").fill(label)
                page.get_by_role("button", name="Add", exact=True).click()
                expect(page.get_by_text(label, exact=True)).to_be_visible()
                expect(page.get_by_placeholder("Add a todo...")).to_have_value("")
                page.get_by_role("listitem").filter(has_text=label).get_by_role(
                    "button"
                ).click()
                expect(page.get_by_text(label, exact=True)).to_have_count(0)
                evidence["checks"].append(
                    "unicode/fragment/percent add, form reset and completion"
                )
            else:
                expect(page.get_by_role("heading", name="Runtime QA")).to_be_visible()
                expect(page.locator("#count")).to_have_text("0")
                page.get_by_role("button", name="Increment", exact=True).click()
                expect(page.locator("#count")).to_have_text("1")
                page.get_by_role("button", name="Child output", exact=True).click()
                page.get_by_role("button", name="Fail event", exact=True).click()
                expect(
                    page.get_by_text("An error occurred.", exact=True)
                ).to_be_visible()
                page.get_by_role("button", name="Increment", exact=True).click()
                expect(page.locator("#count")).to_have_text("2")
                evidence["checks"].append(
                    "event state, subprocess output, failure and subsequent event"
                )
                if args.css_path:
                    assert (
                        page.locator('link[rel="preload"][href*="qa.css"]').count() == 0
                    )
                    expect(page.locator("#css-witness")).to_have_css(
                        "color", "rgb(0, 128, 0)"
                    )
                    args.css_path.write_text(
                        "#css-witness { color: rgb(128, 0, 128); }\n"
                    )
                    expect(page.locator("#css-witness")).to_have_css(
                        "color", "rgb(128, 0, 128)"
                    )
                    expect(page.locator("#count")).to_have_text("2")
                    evidence["checks"].append(
                        "CSS HMR without reload or State reset; no development preload"
                    )
                page.get_by_role("link", name="Article seven", exact=True).click()
                expect(page.get_by_role("heading", name="Article 7")).to_be_visible()
                page.set_extra_http_headers({"self": "qa-header"})
                page.goto(args.url.rstrip("/") + "/articles/7?self=1")
                expect(page.get_by_role("heading", name="Article 7")).to_be_visible()
                evidence["checks"].append(
                    "memo route, direct navigation and self query"
                )
            page.screenshot(path=str(args.output / "browser.png"), full_page=True)
            assert not evidence["page_errors"], evidence["page_errors"]
            evidence["status"] = "passed"
        finally:
            if args.css_path:
                args.css_path.write_text(original_css)
            (args.output / "browser.json").write_text(
                json.dumps(evidence, indent=2) + "\n"
            )
            browser.close()


if __name__ == "__main__":
    main()
