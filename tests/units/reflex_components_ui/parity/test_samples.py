"""Tests for ui_parity.samples."""

from typing import Any

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from ui_parity.samples import wait_for_value


class _Page:
    """A page whose expression has one value, which a wait reaches or not."""

    def __init__(self, value: Any, reached: bool):
        self.value = value
        self.reached = reached
        self.waited: list[tuple[str, str, float]] = []

    def wait_for_function(self, expression: str, arg: str, timeout: float) -> None:
        self.waited.append((expression, arg, timeout))
        if not self.reached:
            msg = "Timeout exceeded."
            raise PlaywrightTimeoutError(msg)

    def evaluate(self, expression: str) -> Any:
        return self.value


def test_wait_for_value_waits_for_the_value_as_json():
    page = _Page(["One", "Two"], reached=True)
    wait_for_value(page, "checked()", ["One", "Two"], timeout=250)
    assert page.waited == [
        (
            "expected => JSON.stringify(checked()) === expected",
            '["One","Two"]',
            250,
        )
    ]


def test_wait_for_value_says_what_it_found_instead():
    page = _Page(["Three"], reached=False)
    with pytest.raises(AssertionError) as error:
        wait_for_value(page, "checked()", ["One"])
    assert str(error.value) == "checked() is ['Three'], not ['One']"


def test_wait_for_value_takes_a_value_that_arrived_as_the_wait_ended():
    page = _Page(["One"], reached=False)
    wait_for_value(page, "checked()", ["One"])
    assert page.waited == [
        ("expected => JSON.stringify(checked()) === expected", '["One"]', 5000)
    ]
