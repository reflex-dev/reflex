"""Drive real upload-stream lifecycle cases through independent Chrome sessions."""

import json
import sys
import threading
import time
import traceback
from collections.abc import Callable
from pathlib import Path

import httpx
from playwright.sync_api import Browser, Page, WebSocket, expect, sync_playwright

FRONTEND = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:3111"
BACKEND = sys.argv[3] if len(sys.argv) > 3 else "http://localhost:8111"
OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
RESULTS: dict = {
    "scenarios": [],
    "console": [],
    "page_errors": [],
    "requests": [],
    "websocket_frames": [],
}


def observe(page: Page, label: str) -> None:
    """Record frontend errors and real upload transport lifecycle.

    Args:
        page: The observed browser page.
        label: The browser context's label.
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
        "request",
        lambda request: (
            RESULTS["requests"].append({
                "page": label,
                "phase": "start",
                "url": request.url,
                "time": time.monotonic(),
            })
            if "_upload" in request.url
            else None
        ),
    )
    page.on(
        "requestfinished",
        lambda request: (
            RESULTS["requests"].append({
                "page": label,
                "phase": "finished",
                "url": request.url,
                "time": time.monotonic(),
                "status": request.response().status,
            })
            if "_upload" in request.url
            else None
        ),
    )
    page.on(
        "requestfailed",
        lambda request: RESULTS["requests"].append({
            "page": label,
            "phase": "failed",
            "url": request.url,
            "time": time.monotonic(),
            "failure": request.failure,
        }),
    )

    def websocket(socket: WebSocket):
        """Record socket deltas used by ordinary and late recovery events.

        Args:
            socket: The observed websocket.
        """
        socket.on(
            "framereceived",
            lambda payload: RESULTS["websocket_frames"].append({
                "page": label,
                "payload": str(payload)[:3000],
                "time": time.monotonic(),
            }),
        )

    page.on("websocket", websocket)


def open_page(browser: Browser, label: str) -> Page:
    """Open an independent token/session and wait for hydration.

    Args:
        browser: The test browser.
        label: The context's evidence label.

    Returns:
        A hydrated page in a fresh browser context.
    """
    page = browser.new_context().new_page()
    observe(page, label)
    response = page.goto(FRONTEND, wait_until="networkidle")
    assert response is not None
    assert response.status == 200
    expect(page.locator("#token")).not_to_be_empty()
    return page


def token(page: Page) -> str:
    """Read the app's own session token.

    Args:
        page: The hydrated browser page.

    Returns:
        The test browser's token.
    """
    return page.locator("#token").inner_text()


def text(page: Page, selector: str, value: str) -> None:
    """Assert a visible result and retain its expected/actual values.

    Args:
        page: The browser page.
        selector: The target CSS selector.
        value: The expected text.
    """
    expect(page.locator(selector)).to_have_text(value, timeout=12000)
    RESULTS["scenarios"][-1]["assertions"].append({
        "selector": selector,
        "expected": value,
        "actual": page.locator(selector).inner_text(),
    })


def upload(page: Page, name: str, chunked: bool = False) -> int:
    """Submit a real browser multipart upload from an in-memory fixture.

    Args:
        page: The browser page.
        name: The fixture's filename.
        chunked: Whether to use the streamed-chunk upload UI.

    Returns:
        The uploaded payload's byte length.
    """
    payload = b"published-alpha upload bytes # percent %\n" * (8000 if chunked else 1)
    root = "chunked" if chunked else "buffered"
    page.locator(f"#{root} input[type=file]").set_input_files({
        "name": name,
        "mimeType": "text/plain",
        "buffer": payload,
    })
    page.click("#upload-chunks" if chunked else "#upload")
    return len(payload)


def backend() -> dict:
    """Read live event/span evidence from the actual backend process.

    Returns:
        The process's recorded events and completed spans.
    """
    return httpx.get(BACKEND + "/api/evidence", timeout=5).json()


def phases(label: str, client_token: str) -> list[dict]:
    """Select a phase belonging to one real browser session.

    Args:
        label: The phase identifier.
        client_token: The browser token.

    Returns:
        Matching backend records.
    """
    return [
        record
        for record in backend()["records"]
        if record["label"] == label and record["token"] == client_token
    ]


def wait_phase(label: str, client_token: str) -> dict:
    """Wait briefly for a phase from the real backend event processor.

    Args:
        label: The phase identifier.
        client_token: The browser token.

    Returns:
        The matching backend phase.
    """
    deadline = time.monotonic() + 6
    while time.monotonic() < deadline:
        matches = phases(label, client_token)
        if matches:
            return matches[-1]
        time.sleep(0.05)
    message = f"No backend phase {label} for {client_token}"
    raise AssertionError(message)


def concurrent(browser: Browser) -> None:
    """Verify independent concurrent uploads and chained completion responses.

    Args:
        browser: The test browser.
    """
    first = open_page(browser, "concurrent-a")
    second = open_page(browser, "concurrent-b")
    assert token(first) != token(second)
    size = upload(first, "first.txt")
    upload(second, "second.txt")
    for page, name in ((first, "first.txt"), (second, "second.txt")):
        text(page, "#upload-status", "done:" + name)
        text(page, "#uploaded-bytes", str(size))
        text(page, "#upload-count", "1")
        start = wait_phase("upload.start", token(page))
        tail = wait_phase("upload.tail_start", token(page))
        assert start["parent_txid"] is None
        assert tail["parent_txid"] == start["txid"]
        assert start["txid"] != tail["txid"]
    first.screenshot(path=OUT / "concurrent-first.png", full_page=True)
    second.screenshot(path=OUT / "concurrent-second.png", full_page=True)
    first.context.close()
    second.context.close()
    finished = [
        record
        for record in RESULTS["requests"]
        if record["phase"] == "finished" and record["page"].startswith("concurrent")
    ]
    assert len(finished) == 2
    assert all(record["status"] == 200 for record in finished)
    records = backend()["records"]
    ends = [
        record
        for record in records
        if record["label"] == "upload.tail_end"
        and record["detail"] in ("first.txt", "second.txt")
    ]
    assert len(ends) == 2
    assert all(
        record["time"] >= min(end["time"] for end in ends) for record in finished
    )


def unrelated(browser: Browser) -> None:
    """Show a buffered response ends without adopting another client's slow event.

    Args:
        browser: The test browser.
    """
    first = open_page(browser, "unrelated-upload")
    second = open_page(browser, "unrelated-ordinary")
    with first.expect_event(
        "requestfinished",
        predicate=lambda request: "_upload" in request.url,
        timeout=10000,
    ):
        upload(first, "quick.txt")
        text(first, "#upload-status", "received:quick.txt")
        second.click("#delayed")
        wait_phase("delayed.start", token(second))
        text(first, "#upload-status", "done:quick.txt")
    text(second, "#delayed-count", "0")
    text(second, "#delayed-count", "1")
    first_end = wait_phase("upload.tail_end", token(first))
    second_end = wait_phase("delayed.end", token(second))
    assert second_end["time"] - first_end["time"] > 0.3
    RESULTS["scenarios"][-1]["timing_separation_seconds"] = (
        second_end["time"] - first_end["time"]
    )
    first.context.close()
    second.context.close()


def disconnect(browser: Browser) -> None:
    """Disconnect an uploading browser while another client's ordinary event runs.

    Args:
        browser: The test browser.
    """
    first = open_page(browser, "disconnect-upload")
    second = open_page(browser, "disconnect-other")
    first_token = token(first)
    second_token = token(second)
    upload(first, "slow-disconnect.txt")
    text(first, "#upload-status", "received:slow-disconnect.txt")
    wait_phase("upload.tail_start", first_token)
    second.click("#delayed")
    wait_phase("delayed.start", second_token)
    first.context.close()
    text(second, "#delayed-count", "1")
    wait_phase("upload.tail_cancel", first_token)
    wait_phase("delayed.end", second_token)
    assert not phases("delayed.cancel", second_token)
    second.click("#ordinary")
    text(second, "#ordinary-count", "1")
    second.context.close()


def navigation(browser: Browser) -> None:
    """Cancel the old on-load chain while a buffered upload remains in flight.

    Args:
        browser: The test browser.
    """
    page = open_page(browser, "navigation")
    client_token = token(page)
    upload(page, "slow-navigation.txt")
    text(page, "#upload-status", "received:slow-navigation.txt")
    page.click("#slow-link")
    text(page, "#nav-status", "slow-started")
    page.click("#new-link")
    text(page, "#nav-status", "new-loaded")
    cancelled = wait_phase("nav.cancel", client_token)
    new = wait_phase("nav.new", client_token)
    assert not phases("nav.end", client_token)
    text(page, "#upload-status", "done:slow-navigation.txt")
    end = wait_phase("upload.tail_end", client_token)
    assert cancelled["time"] < end["time"]
    assert new["time"] < end["time"]
    page.screenshot(path=OUT / "navigation.png", full_page=True)
    page.context.close()


def recovery(browser: Browser) -> None:
    """Verify a failed upload's delayed recovery delta reaches the client by socket.

    Args:
        browser: The test browser.
    """
    page = open_page(browser, "recovery")
    client_token = token(page)
    upload(page, "fail.txt")
    text(page, "#recovered", "1")
    text(page, "#upload-status", "recovered")
    end = wait_phase("recovery.end", client_token)
    response_end = wait_phase("response.exit", client_token)
    assert response_end["time"] < end["time"]
    RESULTS["scenarios"][-1]["late_delta_separation_seconds"] = (
        end["time"] - response_end["time"]
    )
    frames = [
        record
        for record in RESULTS["websocket_frames"]
        if record["page"] == "recovery" and '"recovered' in record["payload"]
    ]
    assert frames
    page.click("#ordinary")
    text(page, "#ordinary-count", "1")
    page.screenshot(path=OUT / "recovery.png", full_page=True)
    page.context.close()


def http_disconnect(browser: Browser) -> None:
    """Disconnect a real slow HTTP stream without cancelling another browser's event.

    Args:
        browser: The test browser.
    """
    first = open_page(browser, "http-stream-owner")
    second = open_page(browser, "http-stream-other")
    first_token = token(first)
    second_token = token(second)
    received = threading.Event()
    close = threading.Event()
    result = {}

    def consumer() -> None:
        """Consume one real NDJSON delta and close the network response on demand."""
        try:
            with (
                httpx.Client(timeout=8) as client,
                client.stream(
                    "POST", BACKEND + "/api/stream", params={"token": first_token}
                ) as response,
            ):
                result["status"] = response.status_code
                for line in response.iter_lines():
                    result["first_delta"] = json.loads(line)
                    received.set()
                    assert close.wait(timeout=4)
                    break
        except Exception:
            result["error"] = traceback.format_exc()
            received.set()

    thread = threading.Thread(target=consumer, daemon=True)
    thread.start()
    assert received.wait(timeout=5)
    assert result.get("status") == 200
    assert "error" not in result
    second.click("#delayed")
    wait_phase("delayed.start", second_token)
    close.set()
    thread.join(timeout=3)
    assert not thread.is_alive()
    wait_phase("http.cancel", first_token)
    text(second, "#delayed-count", "1")
    assert not phases("delayed.cancel", second_token)
    second.click("#ordinary")
    text(second, "#ordinary-count", "1")
    RESULTS["scenarios"][-1]["http_consumer"] = result
    first.context.close()
    second.context.close()


def tracing(browser: Browser) -> None:
    """Assert request-span lineage for chunked uploads and custom HTTP event enqueue.

    Args:
        browser: The test browser.
    """
    page = open_page(browser, "tracing")
    client_token = token(page)
    size = upload(page, "chunks.txt", chunked=True)
    text(page, "#chunk-done", "done")
    text(page, "#chunk-bytes", str(size))
    response = httpx.post(
        BACKEND + "/api/enqueue", params={"token": client_token}, timeout=5
    )
    assert response.status_code == 200
    text(page, "#api-count", "1")
    parent = wait_phase("api.parent", client_token)
    child = wait_phase("api.child", client_token)
    chunk = wait_phase("chunk.start", client_token)
    assert parent["parent_txid"] is None
    assert chunk["parent_txid"] is None
    assert child["parent_txid"] == parent["txid"]
    data = backend()
    spans = data["spans"]
    events = [span for span in spans if "reflex.event.txid" in span["attributes"]]
    by_txid = {span["attributes"]["reflex.event.txid"]: span for span in events}
    by_spanid = {span["span_id"]: span for span in spans}
    for top in (parent, chunk):
        span = by_txid[top["txid"]]
        assert span["kind"] == "INTERNAL"
        assert "reflex.event.parent_txid" not in span["attributes"]
        assert by_spanid[span["parent_span_id"]]["kind"] == "SERVER"
    child_span = by_txid[child["txid"]]
    assert child_span["attributes"]["reflex.event.parent_txid"] == parent["txid"]
    assert child_span["parent_span_id"] == by_txid[parent["txid"]]["span_id"]
    top_buffered = [
        span
        for span in events
        if span["attributes"].get("reflex.event.name", "").endswith(".buffered")
    ]
    assert len(top_buffered) >= 6
    assert all(
        "reflex.event.parent_txid" not in span["attributes"] for span in top_buffered
    )
    RESULTS["scenarios"][-1]["lineage_assertions"] = {
        "chunk_txid": chunk["txid"],
        "api_parent_txid": parent["txid"],
        "api_child_txid": child["txid"],
        "buffered_top_level_spans": len(top_buffered),
    }
    (OUT / "backend-evidence.json").write_text(json.dumps(data, indent=2) + "\n")
    page.context.close()


def scenario(name: str, callback: Callable[[], None]) -> None:
    """Run an independent scenario and retain failure evidence for review.

    Args:
        name: The scenario identifier.
        callback: The scenario's browser assertions.
    """
    current = {"name": name, "assertions": [], "started": time.monotonic()}
    RESULTS["scenarios"].append(current)
    try:
        callback()
        current["status"] = "pass"
    except Exception:
        current["status"] = "fail"
        current["traceback"] = traceback.format_exc()
    current["duration_seconds"] = round(time.monotonic() - current["started"], 3)
    (OUT / "browser-results.json").write_text(json.dumps(RESULTS, indent=2) + "\n")
    print(
        json.dumps({
            "name": name,
            "status": current["status"],
            "assertions": len(current["assertions"]),
            "duration_seconds": current["duration_seconds"],
            "traceback": current.get("traceback"),
        }),
        flush=True,
    )


def main() -> None:
    """Run all real-network upload-stream cases in a separate Chrome instance."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            headless=True,
        )
        RESULTS["browser_version"] = browser.version
        for name, callback in (
            ("concurrent", concurrent),
            ("unrelated", unrelated),
            ("disconnect", disconnect),
            ("navigation", navigation),
            ("recovery", recovery),
            ("http_disconnect", http_disconnect),
            ("tracing", tracing),
        ):
            scenario(name, lambda callback=callback: callback(browser))
        browser.close()
    (OUT / "backend-evidence-final.json").write_text(
        json.dumps(backend(), indent=2) + "\n"
    )
    (OUT / "browser-results.json").write_text(json.dumps(RESULTS, indent=2) + "\n")
    if any(record["status"] != "pass" for record in RESULTS["scenarios"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
