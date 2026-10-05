"""Corrupt this app's Redis session pickles and assert browser recovery."""

import json
import sys
import time
import traceback
from pathlib import Path

import redis
from playwright.sync_api import Browser, Page, expect, sync_playwright

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
STORE = redis.Redis(host="localhost", port=9141, db=5)
RESULTS = {
    "database": 5,
    "initial_dbsize": STORE.dbsize(),
    "scenarios": [],
    "console": [],
    "page_errors": [],
    "request_failures": [],
    "http_errors": [],
    "session_tokens": [],
}


def observe(page: Page, label: str) -> None:
    """Record browser and transport diagnostics.

    Args:
        page: The observed page.
        label: Its evidence identifier.
    """
    page.on(
        "console",
        lambda message: RESULTS["console"].append({
            "page": label,
            "type": message.type,
            "text": message.text,
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


def value(page: Page, selector: str, expected: str) -> None:
    """Assert one rendered value and record its actual text.

    Args:
        page: The browser page.
        selector: The assertion target.
        expected: The required text.
    """
    expect(page.locator(selector)).to_have_text(expected, timeout=15000)
    RESULTS["scenarios"][-1]["assertions"].append({
        "selector": selector,
        "expected": expected,
        "actual": page.locator(selector).inner_text(),
    })


def open_page(browser: Browser, label: str):
    """Open a separate hydrated browser session.

    Args:
        browser: The shared browser process.
        label: Its evidence identifier.

    Returns:
        A context, page, and unique session token.
    """
    context = browser.new_context()
    page = context.new_page()
    observe(page, label)
    response = page.goto("http://localhost:3111", wait_until="networkidle")
    assert response.status == 200
    expect(page.locator("#token")).not_to_be_empty()
    token = page.locator("#token").inner_text()
    assert token not in RESULTS["session_tokens"]
    RESULTS["session_tokens"].append(token)
    return context, page, token


def state_key(page: Page, token: str, selector: str) -> str:
    """Get an exact stored key from the app's concrete state class name.

    Args:
        page: The hydrated page.
        token: Its own session token.
        selector: The displayed class-name element.

    Returns:
        The exact session state key in database 5.
    """
    key = token + "_" + page.locator(selector).inner_text()
    assert STORE.exists(key), key
    return key


def scenario(name: str) -> None:
    """Start one evidence scenario.

    Args:
        name: The scenario's description.
    """
    RESULTS["scenarios"].append({"name": name, "assertions": []})


try:
    assert STORE.ping()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            headless=True,
        )
        RESULTS["browser_version"] = browser.version
        scenario(
            "Redis persistence, component independence, inherited background mutation and concurrent sessions"
        )
        context, page, token = open_page(browser, "persistence")
        other_context, other, other_token = open_page(browser, "independent")
        page.evaluate(
            "for(let i=0;i<12;i++) document.querySelector('#increment').click()"
        )
        other.evaluate(
            "for(let i=0;i<9;i++) document.querySelector('#increment').click()"
        )
        value(page, "#count", "12")
        value(page, "#audit-count", "12")
        value(other, "#count", "9")
        value(other, "#audit-count", "9")
        page.click("#a-increment")
        page.click("#a-increment")
        page.click("#b-increment")
        page.click("#background")
        value(page, "#a-count", "2")
        value(page, "#a-checksum", "5")
        value(page, "#b-count", "1")
        value(page, "#b-checksum", "2")
        value(page, "#worker-done", "2")
        value(page, "#items", '["seed","alpha","beta"]')
        value(page, "#audit-count", "14")
        page.reload(wait_until="networkidle")
        value(page, "#count", "12")
        value(page, "#audit-count", "14")
        value(page, "#a-count", "2")
        value(page, "#a-checksum", "5")
        value(page, "#b-count", "1")
        value(page, "#worker-done", "2")
        value(page, "#items", '["seed","alpha","beta"]')
        value(other, "#count", "9")
        RESULTS["scenarios"][-1]["stored_keys"] = [
            key.decode() for key in STORE.scan_iter(match=token + "_*")
        ]
        page.screenshot(path=str(OUT / "redis-persistence.png"))
        context.close()
        other_context.close()
        for name, payload in (
            ("truncated pickle", None),
            ("empty pickle", b""),
            ("invalid pickle opcode", b"not a valid pickle"),
            ("removed module", b"cdefinitely_missing_alpha_module\nMissingClass\n."),
            ("removed class", b"credis_probe.redis_probe\nMissingRemovedClass\n."),
        ):
            scenario(name + " ordinary state recovers on next browser event")
            context, page, token = open_page(browser, name)
            page.click("#increment")
            page.click("#increment")
            page.click("#a-increment")
            page.click("#a-increment")
            value(page, "#count", "2")
            value(page, "#a-count", "2")
            key = state_key(page, token, "#state-name")
            original = STORE.get(key)
            payload = original[:12] if payload is None else payload
            STORE.set(key, payload, ex=120)
            assert STORE.get(key) == payload
            start = time.monotonic()
            page.click("#increment")
            value(page, "#count", "1")
            value(page, "#audit-count", "1")
            value(page, "#a-count", "2")
            value(page, "#a-checksum", "5")
            value(page, "#b-count", "0")
            replacement = STORE.get(key)
            assert replacement != payload
            assert len(replacement) > 12
            RESULTS["scenarios"][-1].update({
                "state_key": key,
                "original_bytes": len(original),
                "corrupted_bytes": len(payload),
                "replacement_bytes": len(replacement),
                "recovery_seconds": round(time.monotonic() - start, 3),
            })
            page.click("#increment")
            value(page, "#count", "2")
            page.reload(wait_until="networkidle")
            value(page, "#count", "2")
            value(page, "#a-count", "2")
            context.close()
        scenario("Truncated ComponentState recovers independently")
        context, page, token = open_page(browser, "component-corruption")
        for _ in range(3):
            page.click("#increment")
            page.click("#b-increment")
        page.click("#a-increment")
        page.click("#a-increment")
        value(page, "#a-count", "2")
        value(page, "#b-count", "3")
        key = state_key(page, token, "#a-state-name")
        original = STORE.get(key)
        STORE.set(key, original[:12], ex=120)
        page.click("#a-increment")
        value(page, "#a-count", "1")
        value(page, "#a-checksum", "2")
        value(page, "#b-count", "3")
        value(page, "#b-checksum", "9")
        value(page, "#count", "3")
        value(page, "#audit-count", "3")
        RESULTS["scenarios"][-1]["state_key"] = key
        page.reload(wait_until="networkidle")
        value(page, "#a-count", "1")
        value(page, "#b-count", "3")
        page.screenshot(path=str(OUT / "component-recovery.png"))
        context.close()
        browser.close()
    assert not RESULTS["page_errors"], RESULTS["page_errors"]
    assert not RESULTS["request_failures"], RESULTS["request_failures"]
    assert not RESULTS["http_errors"], RESULTS["http_errors"]
    assert not [entry for entry in RESULTS["console"] if entry["type"] == "error"]
    RESULTS["status"] = "passed"
except Exception:
    RESULTS["status"] = "failed"
    RESULTS["traceback"] = traceback.format_exc()
    raise
finally:
    (OUT / "browser-results.json").write_text(json.dumps(RESULTS, indent=2))
