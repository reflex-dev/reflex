"""Exercise PR251 memoized AG Grid cells in inline, State and API definitions."""

import json
import os
import re
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

OUTPUT = Path(os.environ["QA_OUTPUT"])
BASE = os.environ.get("QA_FRONTEND", "http://localhost:3131")


def main() -> None:
    """Verify real cell events, shared row counters and dynamic bundle execution."""
    (OUTPUT / "logs").mkdir(parents=True, exist_ok=True)
    (OUTPUT / "screenshots").mkdir(parents=True, exist_ok=True)
    evidence = {
        "results": [],
        "console": [],
        "page_errors": [],
        "failed_requests": [],
        "http_errors": [],
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 2200, "height": 1200})
        page = context.new_page()
        page.on(
            "console",
            lambda message: evidence["console"].append(
                {
                    "type": message.type,
                    "text": message.text,
                    "location": message.location,
                }
            ),
        )
        page.on("pageerror", lambda error: evidence["page_errors"].append(str(error)))
        page.on(
            "requestfailed",
            lambda request: evidence["failed_requests"].append(
                {"url": request.url, "failure": request.failure}
            ),
        )
        page.on(
            "response",
            lambda response: (
                evidence["http_errors"].append(
                    {"url": response.url, "status": response.status}
                )
                if response.status >= 400
                else None
            ),
        )
        try:
            page.goto(BASE + "/formatters-direct")
            counts = [0, 0]
            for label in ("Inline", "State", "API"):
                page.get_by_role("tab", name=label, exact=True).click()
                if label == "API":
                    page.get_by_role(
                        "button", name="Set column defs", exact=True
                    ).click()
                grid = page.locator('[role="tabpanel"][data-state="active"]')
                first = grid.locator(
                    '.ag-row[row-index="0"] [col-id="row counter"] button'
                )
                second = grid.locator(
                    '.ag-row[row-index="1"] [col-id="row counter"] button'
                )
                expect(first).to_have_text(
                    re.compile(rf"^{counts[0]}\s*\("), timeout=20000
                )
                expect(second).to_have_text(re.compile(rf"^{counts[1]}\s*\("))
                expect(
                    grid.locator('.ag-row[row-index="0"] [col-id="percent"]')
                ).to_have_text("56.00%")
                expect(
                    grid.locator('.ag-row[row-index="0"] [col-id="currency number"]')
                ).to_have_text("$12,345.68")
                first.click()
                counts[0] += 1
                expect(first).to_have_text(
                    re.compile(rf"^{counts[0]}\s*\(\d{{2}}:\d{{2}}\)")
                )
                expect(second).to_have_text(re.compile(rf"^{counts[1]}\s*\("))
                second.click()
                counts[1] += 1
                expect(second).to_have_text(
                    re.compile(rf"^{counts[1]}\s*\(\d{{2}}:\d{{2}}\)")
                )
                grid.locator(
                    '.ag-row[row-index="0"] [col-id="raw data"] button'
                ).click()
                dialog = page.get_by_role("dialog")
                expect(dialog).to_contain_text("Raw Row Data")
                expect(dialog).to_contain_text("John")
                page.keyboard.press("Escape")
                expect(dialog).not_to_be_visible()
                if label == "API":
                    page.get_by_role(
                        "button", name="Clear column defs", exact=True
                    ).click()
                    expect(grid.locator('[col-id="row counter"]')).to_have_count(0)
                    page.get_by_role(
                        "button", name="Set column defs", exact=True
                    ).click()
                    expect(first).to_have_text(re.compile(rf"^{counts[0]}\s*\("))
                result = {
                    "case": f"memo_renderer_{label.lower()}",
                    "passed": True,
                    "counts": counts.copy(),
                    "first_button": first.inner_text(),
                    "second_button": second.inner_text(),
                }
                evidence["results"].append(result)
                page.screenshot(
                    path=OUTPUT / "screenshots" / f"formatter-{label.lower()}.png",
                    full_page=True,
                )
                print(json.dumps(result), flush=True)
            assert not evidence["page_errors"], evidence["page_errors"]
            assert not evidence["http_errors"], evidence["http_errors"]
            unexpected = [
                message
                for message in evidence["console"]
                if message["type"] in {"error", "warning"}
                and not message["text"].startswith("*")
            ]
            assert not unexpected, unexpected
        except Exception as error:
            evidence["failure"] = str(error)
            page.screenshot(
                path=OUTPUT / "screenshots/formatters-failure.png", full_page=True
            )
            raise
        finally:
            (OUTPUT / "logs/formatters-browser.json").write_text(
                json.dumps(evidence, indent=2) + "\n"
            )
            context.close()
            browser.close()


if __name__ == "__main__":
    main()
