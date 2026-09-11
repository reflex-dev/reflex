"""A second dev harness AFTER AppHarnessProd ran export() in this process.

export() sets REFLEX_ENV_MODE=prod process-wide; before the 0.9.9 fix the next
dev harness compiled in leaked prod mode. This asserts it does not.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

import httpx
import pytest
from conftest import record
from harness_app import DemoApp, PWText, browser, new_page, read_state, vite_client_status

from reflex.testing import AppHarness

SHOTS = Path(os.environ.get("TA_SHOTS", "/tmp"))
CONSOLE: list = []
NETWORK: list = []


@pytest.fixture(scope="module")
def harness2(tmp_path_factory) -> Generator[AppHarness, None, None]:
    with AppHarness.create(
        root=tmp_path_factory.mktemp("dev_app2"), app_source=DemoApp
    ) as h:
        yield h


def test_env_mode_not_leaked_from_prod(harness2: AppHarness):
    import reflex
    from reflex_base.environment import environment

    mode = environment.REFLEX_ENV_MODE.get()
    record("dev2_env_mode", str(mode))
    assert mode == reflex.constants.Env.DEV, f"prod mode leaked into dev harness: {mode}"


def test_dev2_is_a_dev_server(harness2: AppHarness):
    with httpx.Client(trust_env=False, timeout=60) as c:
        r = c.get(harness2.frontend_url)
    record("dev2_status", r.status_code)
    record("dev2_vite_client_status", vite_client_status(harness2.frontend_url))
    assert r.status_code == 200
    assert vite_client_status(harness2.frontend_url) == 200, (
        "second dev harness is not a vite dev server (prod mode leaked?)"
    )


def test_dev2_browser_roundtrip(harness2: AppHarness):
    with browser() as b:
        page = new_page(b, CONSOLE, NETWORK)
        page.goto(harness2.frontend_url, wait_until="networkidle", timeout=60000)
        page.wait_for_selector("#token")
        token = harness2.poll_for_content(PWText(page, "#token"), timeout=30)
        page.click("#bump")
        page.wait_for_function("document.querySelector('#count').innerText === '1'", timeout=30000)
        page.screenshot(path=str(SHOTS / "dev2_after_bump.png"))
        assert page.inner_text("#summary") == "1/1/2"

    st = read_state(harness2, token, ["count", "items"])
    record("dev2_state", st)
    assert st["count"] == 1
    assert st["items"] == ["i1"]


def test_dev2_console_clean(harness2: AppHarness):
    errs = [m for m in CONSOLE if m["type"] in ("error", "pageerror")]
    record("dev2_console_errors", errs)
    record("dev2_failed_requests", NETWORK)
    assert not errs, errs
