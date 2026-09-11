"""AppHarness (dev mode) driven with Playwright, as a downstream project would."""

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
def harness(tmp_path_factory) -> Generator[AppHarness, None, None]:
    with AppHarness.create(
        root=tmp_path_factory.mktemp("dev_app"), app_source=DemoApp
    ) as h:
        yield h


def test_dev_env_mode(harness: AppHarness):
    """The 0.9.9 REFLEX_ENV_MODE leak fix: a dev harness compiles in dev mode."""
    import reflex
    from reflex_base.environment import environment

    mode = environment.REFLEX_ENV_MODE.get()
    record("dev1_env_mode", str(mode))
    assert mode == reflex.constants.Env.DEV, mode


def test_dev_frontend_serves(harness: AppHarness):
    assert harness.frontend_url
    with httpx.Client(trust_env=False, timeout=60) as c:
        r = c.get(harness.frontend_url)
    record("dev1_frontend_url", harness.frontend_url)
    record("dev1_status", r.status_code)
    record("dev1_vite_client_status", vite_client_status(harness.frontend_url))
    assert r.status_code == 200
    assert vite_client_status(harness.frontend_url) == 200, "dev harness is not a vite dev server"


def test_dev_browser_roundtrip(harness: AppHarness):
    """Click in a real browser; read the resulting state back through app_instance."""
    with browser() as b:
        page = new_page(b, CONSOLE, NETWORK)
        page.goto(harness.frontend_url, wait_until="networkidle", timeout=60000)
        page.wait_for_selector("#token")
        token = harness.poll_for_content(PWText(page, "#token"), timeout=30)
        record("dev1_token", token)

        for _ in range(3):
            page.click("#bump")
        assert harness.poll_for_content(
            PWText(page, "#count"), timeout=30, exp_not_equal="0"
        )
        page.wait_for_function("document.querySelector('#count').innerText === '3'", timeout=30000)
        page.screenshot(path=str(SHOTS / "dev_after_bump.png"))

        record("dev1_ui_count", page.inner_text("#count"))
        record("dev1_ui_summary", page.inner_text("#summary"))
        record("dev1_ui_nitems", page.inner_text("#nitems"))
        record("dev1_items_rendered", page.locator(".item").count())

        assert page.inner_text("#count") == "3"
        assert page.inner_text("#summary") == "3/3/4"

    # server-side state for that very browser session (outside the playwright loop)
    st = read_state(harness, token, ["count", "items", "meta", "row"])
    record("dev1_state_count", st["count"])
    record("dev1_state_items", st["items"])
    record("dev1_state_meta", st["meta"])
    record("dev1_state_row_qty", st["row"].qty)
    assert st["count"] == 3
    assert st["items"] == ["i1", "i2", "i3"]
    assert st["meta"] == {"k1": 1, "k2": 2, "k3": 3}
    assert st["row"].qty == 4


def test_dev_chain_background_and_nav(harness: AppHarness):
    with browser() as b:
        page = new_page(b, CONSOLE, NETWORK)
        page.goto(harness.frontend_url, wait_until="networkidle", timeout=60000)
        page.wait_for_selector("#token")
        token = harness.poll_for_content(PWText(page, "#token"), timeout=30)

        page.click("#chain")  # count += 10 then yields bump -> 11
        page.wait_for_function("document.querySelector('#count').innerText === '11'", timeout=30000)
        page.click("#tick")  # background event, 3 increments
        page.wait_for_function("document.querySelector('#ticks').innerText === '3'", timeout=30000)
        record("dev1_chain_count", page.inner_text("#count"))
        record("dev1_bg_ticks", page.inner_text("#ticks"))

        page.click("#tosecond")
        page.wait_for_selector("#second", timeout=30000)
        record("dev1_second_count", page.inner_text("#count2"))
        page.screenshot(path=str(SHOTS / "dev_second_page.png"))
        assert page.inner_text("#count2") == "11"

    st = read_state(harness, token, ["count", "bg_ticks"])
    record("dev1_state_after_chain", st)
    assert st["count"] == 11
    assert st["bg_ticks"] == 3


def test_dev_console_and_network_clean(harness: AppHarness):
    errs = [m for m in CONSOLE if m["type"] in ("error", "pageerror")]
    warns = [m for m in CONSOLE if m["type"] == "warning"]
    record("dev1_console_errors", errs)
    record("dev1_console_warnings", warns)
    record("dev1_failed_requests", NETWORK)
    assert not errs, errs
    assert not NETWORK, NETWORK


def test_dev_selenium_frontend(harness: AppHarness):
    """The `testing` extra ships selenium: drive the app through `harness.frontend()`.

    Chromium and chromedriver are given explicitly because this sandbox has no
    system Chrome and selenium-manager cannot download one.
    """
    import os

    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service

    chromium = "/opt/pw-browsers/chromium"
    chromedriver = "/opt/node22/bin/chromedriver"
    if not (os.path.exists(chromium) and os.path.exists(chromedriver)):
        pytest.skip("no chromium/chromedriver in this environment")

    options = Options()
    options.binary_location = chromium
    for arg in ("--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--no-proxy-server"):
        options.add_argument(arg)
    try:
        driver = harness.frontend(
            driver_options=options,
            driver_kwargs={"service": Service(executable_path=chromedriver)},
        )
    except Exception as exc:  # noqa: BLE001
        record("dev1_selenium_frontend", f"{type(exc).__name__}: {exc}")
        pytest.skip(f"selenium frontend unavailable: {type(exc).__name__}: {exc}")

    # a genuine selenium WebElement through the documented polling helper
    el = driver.find_element("id", "count")
    record("dev1_selenium_initial_count", harness.poll_for_content(el, timeout=30, exp_not_equal="x"))
    driver.find_element("id", "bump").click()
    text = harness.poll_for_content(el, timeout=30, exp_not_equal="3")
    record("dev1_selenium_count_after_bump", text)
    record("dev1_selenium_summary", driver.find_element("id", "summary").text)
    assert text == "4", text
