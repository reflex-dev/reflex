from pathlib import Path

import pytest
from selenium.webdriver.common.by import By

from reflex.testing import AppHarness, WebDriver


def get_session_storage(driver: WebDriver, key: str) -> str:
    return driver.execute_script(
        "return window.sessionStorage.getItem(arguments[0]);", key
    )


@pytest.fixture()
def counter_app():
    with AppHarness.create(root=Path(__file__).parent.parent) as harness:
        yield harness


@pytest.mark.asyncio
async def test_counter_app(counter_app: AppHarness):
    driver = counter_app.frontend()

    token = None

    def _poll_token():
        nonlocal token
        token = get_session_storage(driver, "token")
        return token

    assert AppHarness._poll_for(_poll_token), "token not found"

    state_name = counter_app.get_state_name("State")
    full_state_name = counter_app.get_full_state_name("State")

    async def _get_backend_state():
        root_state = await counter_app.get_state(f"{token}_{full_state_name}")
        return root_state.substates[state_name]

    count = driver.find_element(By.TAG_NAME, "h1")
    assert counter_app.poll_for_content(count) == "0"

    decrement = driver.find_element(By.XPATH, "//button[text()='Decrement']")
    randomize = driver.find_element(By.XPATH, "//button[text()='Randomize']")
    increment = driver.find_element(By.XPATH, "//button[text()='Increment']")

    decrement.click()
    assert counter_app.poll_for_content(count, exp_not_equal="0") == "-1"
    assert (await _get_backend_state()).count == -1

    increment.click()
    assert counter_app.poll_for_content(count, exp_not_equal="-1") == "0"
    increment.click()
    assert counter_app.poll_for_content(count, exp_not_equal="0") == "1"
    assert (await _get_backend_state()).count == 1

    randomize.click()
    random_count = counter_app.poll_for_content(count, exp_not_equal="1")
    assert (await _get_backend_state()).count == int(random_count)
    decrement.click()
    dec_value = str(int(random_count) - 1)
    assert counter_app.poll_for_content(count, exp_not_equal=random_count) == dec_value
    increment.click()
    assert counter_app.poll_for_content(count, exp_not_equal=dec_value) == random_count
    assert count.text == random_count
