"""AppHarnessProd in the SAME pytest process, after a dev harness has run."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

import httpx
import pytest
from conftest import record
from harness_app import DemoApp, PWText, browser, new_page, read_state, vite_client_status

from reflex.testing import AppHarnessProd

SHOTS = Path(os.environ.get("TA_SHOTS", "/tmp"))
CONSOLE: list = []
NETWORK: list = []


@pytest.fixture(scope="module")
def prod_harness(tmp_path_factory) -> Generator[AppHarnessProd, None, None]:
    with AppHarnessProd.create(
        root=tmp_path_factory.mktemp("prod_app"), app_source=DemoApp
    ) as h:
        yield h


def test_prod_frontend_serves(prod_harness: AppHarnessProd):
    assert prod_harness.frontend_url
    with httpx.Client(trust_env=False, timeout=60) as c:
        r = c.get(prod_harness.frontend_url)
    record("prod_frontend_url", prod_harness.frontend_url)
    record("prod_status", r.status_code)
    record("prod_vite_client_status", vite_client_status(prod_harness.frontend_url))
    assert r.status_code == 200
    assert vite_client_status(prod_harness.frontend_url) != 200, "prod harness served a vite dev server"


def test_prod_browser_roundtrip(prod_harness: AppHarnessProd):
    with browser() as b:
        page = new_page(b, CONSOLE, NETWORK)
        page.goto(prod_harness.frontend_url, wait_until="networkidle", timeout=90000)
        page.wait_for_selector("#token", timeout=60000)
        token = prod_harness.poll_for_content(PWText(page, "#token"), timeout=60)
        record("prod_token", token)
        for _ in range(2):
            page.click("#bump")
        page.wait_for_function("document.querySelector('#count').innerText === '2'", timeout=60000)
        page.click("#tick")
        page.wait_for_function("document.querySelector('#ticks').innerText === '3'", timeout=60000)
        page.screenshot(path=str(SHOTS / "prod_after_bump.png"))
        record("prod_ui_count", page.inner_text("#count"))
        record("prod_ui_summary", page.inner_text("#summary"))
        assert page.inner_text("#summary") == "2/2/3"

    st = read_state(prod_harness, token, ["count", "items", "bg_ticks"])
    record("prod_state", st)
    assert st["count"] == 2
    assert st["items"] == ["i1", "i2"]
    assert st["bg_ticks"] == 3


def test_prod_console_and_network_clean(prod_harness: AppHarnessProd):
    errs = [m for m in CONSOLE if m["type"] in ("error", "pageerror")]
    record("prod_console_errors", errs)
    record("prod_console_warnings", [m for m in CONSOLE if m["type"] == "warning"])
    record("prod_failed_requests", NETWORK)
    assert not errs, errs
    assert not NETWORK, NETWORK
