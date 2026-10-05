"""Identical browser flows for existing stable-to-alpha upgraded applications."""

import json
import sys
import traceback
from pathlib import Path

from playwright.sync_api import BrowserContext, Page, expect, sync_playwright


def overkey(
    page: Page, context: BrowserContext, base_url: str, backend_url: str
) -> dict:
    """Complete and reset a real five-second typing round.

    Args:
        page: Browser page.
        context: Browser context.
        base_url: Frontend base URL.
        backend_url: Backend base URL.

    Returns:
        The typed words and visible final metrics.
    """
    page.goto(base_url)
    expect(page.locator("#words .letter").first).to_be_visible(timeout=30000)
    page.get_by_role("combobox").nth(1).click()
    page.get_by_role("option", name="5 seconds", exact=True).click()
    expect(page.get_by_role("combobox").nth(1)).to_contain_text("5 seconds")
    paragraph = page.locator("#words").text_content()
    typed = paragraph[:10]
    input_field = page.locator("input").first
    input_field.focus()
    input_field.press_sequentially(typed, delay=40)
    expect(page.get_by_text("Time's up!", exact=True)).to_be_visible(timeout=15000)
    expect(page.get_by_text("100.00% accuracy", exact=False)).to_be_visible()
    summary = page.get_by_text("100.00% accuracy", exact=False).text_content()
    page.get_by_role("button").first.click()
    expect(page.get_by_role("combobox")).to_have_count(2)
    expect(page.locator("input").first).to_have_value("")
    page.get_by_role("combobox").first.click()
    page.get_by_role("option", name="español", exact=True).click()
    expect(page.get_by_role("combobox").first).to_contain_text("español")
    expect(page.locator("#words .letter").first).to_be_visible()
    return {
        "typed": typed,
        "summary": summary,
        "reset_input": page.locator("input").first.input_value(),
        "language": "español",
    }


def basic_crud(
    page: Page, context: BrowserContext, base_url: str, backend_url: str
) -> dict:
    """Exercise browser CRUD and a database row retained across the upgrade.

    Args:
        page: Browser page.
        context: Browser context.
        base_url: Frontend base URL.
        backend_url: Backend base URL.

    Returns:
        Created record values and the retained row identifier.
    """
    records = context.request.get(backend_url + "/products").json()
    persisted = next((item for item in records if item["code"] == "PERSISTED"), None)
    payload = {
        "code": "PERSISTED",
        "label": "Survives upgrade",
        "image": "/favicon.ico",
        "quantity": 7,
        "category": "baseline",
        "seller": "Ops",
        "sender": "Warehouse",
    }
    if persisted is None:
        response = context.request.post(
            backend_url + "/products", data=json.dumps(payload)
        )
        assert response.ok, response.text()
        persisted = next(
            item
            for item in context.request.get(backend_url + "/products").json()
            if item["code"] == "PERSISTED"
        )
    page.goto(base_url)
    expect(page.get_by_text("(PERSISTED) Survives upgrade", exact=True)).to_be_visible(
        timeout=30000
    )

    def send(method: str, route: str, body: dict | None = None) -> None:
        """Send one request through the app's actual browser controls.

        Args:
            method: HTTP method selected by the user.
            route: Relative backend path.
            body: JSON request body.
        """
        page.get_by_role("combobox").click()
        page.get_by_role("option", name=method, exact=True).click()
        page.locator("input").first.fill(route)
        if body is not None:
            page.locator("textarea").fill(json.dumps(body))
        page.get_by_role("button", name="Send", exact=True).click()
        expect(page.get_by_text("Status:", exact=False)).to_contain_text(
            "200", timeout=15000
        )

    product = {
        "code": "BROWSER-PRODUCT",
        "label": "Created in browser",
        "image": "/favicon.ico",
        "quantity": 11,
        "category": "hardware",
        "seller": "Ops",
        "sender": "Warehouse",
    }
    send("POST", "products", product)
    expect(
        page.get_by_text("(BROWSER-PRODUCT) Created in browser", exact=True)
    ).to_be_visible(timeout=15000)
    record = next(
        item
        for item in context.request.get(backend_url + "/products").json()
        if item["code"] == "BROWSER-PRODUCT"
    )
    send("GET", "products")
    expect(page.locator("pre")).to_contain_text("BROWSER-PRODUCT")
    send(
        "PUT",
        f"products/{record['id']}",
        {"label": "Updated in browser", "quantity": 23},
    )
    expect(
        page.get_by_text("(BROWSER-PRODUCT) Updated in browser", exact=True)
    ).to_be_visible(timeout=15000)
    send("DELETE", f"products/{record['id']}")
    expect(
        page.get_by_text("(BROWSER-PRODUCT) Updated in browser", exact=True)
    ).not_to_be_visible(timeout=15000)
    final_records = context.request.get(backend_url + "/products").json()
    assert all(item["code"] != "BROWSER-PRODUCT" for item in final_records)
    assert (
        next(item for item in final_records if item["code"] == "PERSISTED")["id"]
        == persisted["id"]
    )
    return {
        "persisted_id": persisted["id"],
        "created_id": record["id"],
        "final_records": final_records,
    }


def main() -> None:
    """Run the selected unchanged application flow and save diagnostics."""
    app_name, phase, base_url, backend_url, output_path = sys.argv[1:]
    output = Path(output_path)
    output.mkdir(parents=True, exist_ok=True)
    diagnostics = {
        "console": [],
        "page_errors": [],
        "request_failures": [],
        "http_failures": [],
    }
    result = {"app": app_name, "phase": phase, "base_url": base_url}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        page.set_default_timeout(20000)
        page.on(
            "console",
            lambda item: diagnostics["console"].append({
                "type": item.type,
                "text": item.text,
            }),
        )
        page.on("pageerror", lambda item: diagnostics["page_errors"].append(str(item)))
        page.on(
            "requestfailed",
            lambda item: diagnostics["request_failures"].append({
                "url": item.url,
                "failure": item.failure,
            }),
        )
        page.on(
            "response",
            lambda item: (
                diagnostics["http_failures"].append({
                    "url": item.url,
                    "status": item.status,
                })
                if item.status >= 400
                else None
            ),
        )
        try:
            result["detail"] = {"overkey": overkey, "basic_crud": basic_crud}[app_name](
                page, context, base_url, backend_url
            )
            result["status"] = "passed"
        except Exception as error:
            result.update(
                status="failed", error=str(error), traceback=traceback.format_exc()
            )
        result["diagnostics"] = diagnostics
        page.screenshot(path=str(output / f"{app_name}-{phase}.png"), full_page=True)
        (output / f"{app_name}-{phase}.json").write_text(
            json.dumps(result, indent=2) + "\n"
        )
        print(json.dumps(result), flush=True)  # noqa: T201
        browser.close()
    if result["status"] != "passed" or diagnostics["page_errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
