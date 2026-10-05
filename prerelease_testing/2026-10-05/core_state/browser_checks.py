"""Assert real browser behavior of the published-alpha state dashboard."""

import json
import sys
import time
import traceback
from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import Page, WebSocket, expect, sync_playwright

BASE = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:3111"
RESULTS: dict = {
    "scenarios": [],
    "console": [],
    "page_errors": [],
    "request_failures": [],
    "http_errors": [],
    "websocket_frames": [],
}
OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)


def observe(page: Page, label: str) -> None:
    """Record frontend and transport evidence for a page.

    Args:
        page: The observed browser page.
        label: An identifier for the browser context.
    """
    page.on(
        "console",
        lambda message: RESULTS["console"].append({
            "page": label,
            "type": message.type,
            "text": message.text,
            "location": message.location,
        }),
    )
    page.on(
        "pageerror",
        lambda error: RESULTS["page_errors"].append({
            "page": label,
            "error": str(error),
        }),
    )
    page.on(
        "requestfailed",
        lambda request: RESULTS["request_failures"].append({
            "page": label,
            "url": request.url,
            "error": request.failure,
        }),
    )
    page.on(
        "response",
        lambda response: (
            RESULTS["http_errors"].append({
                "page": label,
                "url": response.url,
                "status": response.status,
            })
            if response.status >= 400
            else None
        ),
    )

    def websocket(socket: WebSocket):
        """Record the first few transport frames.

        Args:
            socket: The browser websocket.
        """
        socket.on(
            "framesent",
            lambda payload: RESULTS["websocket_frames"].append({
                "page": label,
                "direction": "sent",
                "payload": str(payload)[:3000],
            }),
        )
        socket.on(
            "framereceived",
            lambda payload: RESULTS["websocket_frames"].append({
                "page": label,
                "direction": "received",
                "payload": str(payload)[:3000],
            }),
        )

    page.on("websocket", websocket)


def text(page: Page, selector: str, value: str) -> None:
    """Assert a rendered value and append a compact assertion record.

    Args:
        page: The browser page.
        selector: The CSS selector to assert.
        value: The expected text.
    """
    expect(page.locator(selector)).to_have_text(value, timeout=20000)
    RESULTS["scenarios"][-1]["assertions"].append({
        "selector": selector,
        "expected": value,
        "actual": page.locator(selector).inner_text(),
    })


def dashboard(page: Page) -> None:
    """Exercise descriptor ownership, mutations, ComponentState and frontend Vars.

    Args:
        page: The browser page.
    """
    response = page.goto(BASE + "/?self=1", wait_until="networkidle")
    assert response is not None
    assert response.status == 200
    expect(page.locator("#token")).not_to_be_empty()
    text(page, "#parent-count", "2")
    text(page, "#parent-computed", "4")
    text(page, "#child-count", "10")
    text(page, "#child-computed", "30")
    page.click("#child-increment")
    text(page, "#child-count", "11")
    text(page, "#child-computed", "33")
    text(page, "#parent-count", "2")
    page.click("#inherited-increment")
    text(page, "#parent-count", "3")
    text(page, "#parent-computed", "6")
    text(page, "#child-count", "11")
    page.click("#parent-increment")
    text(page, "#parent-count", "4")
    text(page, "#parent-computed", "8")
    page.click("#background")
    text(page, "#worker-done", "2")
    text(page, "#parent-items", '["seed","alpha","beta"]')
    text(page, "#parent-audit", "2")
    page.click("#a-increment")
    page.click("#a-increment")
    text(page, "#a-count", "2")
    text(page, "#a-checksum", "5")
    text(page, "#b-count", "0")
    text(page, "#b-checksum", "0")
    page.click("#b-increment")
    text(page, "#b-count", "1")
    text(page, "#b-checksum", "2")
    text(page, "#a-count", "2")
    text(page, "#reverse-items", "[5,4,3,2,1]")
    text(page, "#empty-reverse", "[]")
    text(page, "#var-slice", "[5,4,3]")
    text(page, "#slice-length", "5")
    text(page, "#reverse-text", "olleh")
    page.click("#positive-step")
    text(page, "#slice-length", "3")
    text(page, "#var-slice", "[]")
    page.click("#negative-step")
    text(page, "#var-slice", "[5,4,3]")
    text(page, "#deep-equality", "equal")
    page.click("#mutate-nested")
    text(page, "#deep-equality", "different")
    text(page, "#nested-value", '{"a":[1,2,4],"b":[3]}')
    page.click("#nested-events")
    text(page, "#nested-first", "1")
    text(page, "#nested-second", "1")
    page.click("#ordinary-event")
    text(page, "#nested-first", "2")
    with page.expect_download() as download_info:
        page.click("#download")
    download = download_info.value
    download.save_as(OUT / "escaped.json")
    assert json.loads((OUT / "escaped.json").read_text()) == {
        "text": "hash# percent% café"
    }
    RESULTS["scenarios"][-1]["assertions"].append({
        "download": download.suggested_filename,
        "value": json.loads((OUT / "escaped.json").read_text()),
    })
    page.reload(wait_until="networkidle")
    text(page, "#parent-count", "4")
    text(page, "#child-count", "11")
    text(page, "#parent-items", '["seed","alpha","beta"]')
    text(page, "#parent-audit", "2")
    text(page, "#a-count", "2")
    page.screenshot(path=OUT / "dashboard.png", full_page=True)


def client(page: Page) -> None:
    """Exercise setter-only memos, late readers and backend-derived defaults.

    Args:
        page: The browser page.
    """
    page.goto(BASE + "/client", wait_until="networkidle")
    expect(page.locator("#token")).not_to_be_empty()
    expect(page.locator("#client-reader")).to_have_count(0)
    page.click("#client-setter")
    page.click("#reveal")
    text(page, "#client-reader", "clicked before mount")
    page.click("#hide")
    expect(page.locator("#client-reader")).to_have_count(0)
    page.click("#client-setter")
    page.click("#reveal")
    text(page, "#client-reader", "clicked before mount")
    expect(page.locator("#backend-reader")).to_have_value("backend default")
    page.click("#backend-setter")
    expect(page.locator("#backend-reader")).to_have_value("changed")
    page.fill("#backend-input", "typed client")
    expect(page.locator("#backend-reader")).to_have_value("typed client")
    page.click("#retrieve")
    text(page, "#received-client", "typed client")
    page.click("#push")
    expect(page.locator("#backend-reader")).to_have_value("pushed")
    page.click("#client-a-increment")
    text(page, "#client-a-count", "1")
    text(page, "#client-a-checksum", "2")
    text(page, "#client-b-count", "0")
    page.screenshot(path=OUT / "client.png", full_page=True)


def shared(first: Page, second: Page) -> None:
    """Verify shared mutations and private events across distinct client tokens.

    Args:
        first: The first browser session.
        second: The second independent browser session.
    """
    room = f"core-room-{time.time_ns()}"
    for page in (first, second):
        page.goto(BASE + "/shared?room=" + room, wait_until="networkidle")
        expect(page.locator("#token")).not_to_be_empty()
        page.click("#join")
    assert first.locator("#token").inner_text() != second.locator("#token").inner_text()
    text(first, "#shared-count", "0")
    text(second, "#shared-count", "0")
    first.click("#shared-increment")
    for page in (first, second):
        text(page, "#shared-count", "1")
        text(page, "#shared-messages", '["message-1"]')
        text(page, "#shared-audit", "1")
    first.click("#private-event")
    text(first, "#private-count", "1")
    text(second, "#private-count", "0")
    second.click("#shared-increment")
    for page in (first, second):
        text(page, "#shared-count", "2")
        text(page, "#shared-messages", '["message-1","message-2"]')
        text(page, "#shared-audit", "2")
    second.reload(wait_until="networkidle")
    text(second, "#shared-count", "2")
    second.click("#leave")
    text(second, "#shared-count", "0")
    text(second, "#shared-audit", "0")
    first.click("#shared-increment")
    text(first, "#shared-count", "3")
    text(second, "#shared-count", "0")
    second.click("#join")
    text(second, "#shared-count", "3")
    text(second, "#shared-audit", "3")
    first.screenshot(path=OUT / "shared-first.png", full_page=True)
    second.screenshot(path=OUT / "shared-second.png", full_page=True)


def scenario(name: str, callback: Callable[[], None]) -> None:
    """Run an independent scenario and retain failures without hiding other coverage.

    Args:
        name: The scenario's identifier.
        callback: The assertions to execute.
    """
    record = {"name": name, "assertions": [], "started": time.time()}
    RESULTS["scenarios"].append(record)
    try:
        callback()
        record["status"] = "pass"
    except Exception:
        record["status"] = "fail"
        record["traceback"] = traceback.format_exc()
    record["duration_seconds"] = round(time.time() - record["started"], 3)
    (OUT / "browser-results.json").write_text(json.dumps(RESULTS, indent=2) + "\n")
    print(
        json.dumps({
            "name": name,
            "status": record["status"],
            "assertions": len(record["assertions"]),
            "duration_seconds": record["duration_seconds"],
            "traceback": record.get("traceback"),
        })
    )


def main() -> None:
    """Launch a fresh browser and run independent dashboard, client and shared tests."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            headless=True,
        )
        contexts = [browser.new_context(accept_downloads=True) for _ in range(4)]
        pages = [context.new_page() for context in contexts]
        for index, page in enumerate(pages):
            observe(page, f"context-{index}")
        scenario("dashboard", lambda: dashboard(pages[0]))
        scenario("client", lambda: client(pages[1]))
        scenario("shared", lambda: shared(pages[2], pages[3]))
        browser.close()
    (OUT / "browser-results.json").write_text(json.dumps(RESULTS, indent=2) + "\n")
    print(
        json.dumps({
            "page_errors": RESULTS["page_errors"],
            "http_errors": RESULTS["http_errors"],
            "request_failures": RESULTS["request_failures"],
            "console_errors": [
                message for message in RESULTS["console"] if message["type"] == "error"
            ],
        })
    )
    if any(record["status"] != "pass" for record in RESULTS["scenarios"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
