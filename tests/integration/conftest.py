"""Shared conftest for all integration tests."""

import pytest
from pytest_mock import MockerFixture

import reflex.app
from reflex.testing import AppHarness, AppHarnessProd


@pytest.fixture(
    scope="session", params=[AppHarness, AppHarnessProd], ids=["dev", "prod"]
)
def app_harness_env(request):
    """Parametrize the AppHarness class to use for the test, either dev or prod.

    Args:
        request: The pytest fixture request object.

    Returns:
        The AppHarness class to use for the test.
    """
    return request.param


@pytest.fixture(autouse=True)
def raise_console_error(request, mocker: MockerFixture):
    """Spy on calls to `console.error` used by the framework.

    Help catch spurious error conditions that might otherwise go unnoticed.

    If a test is marked with `ignore_console_error`, the spy will be ignored
    after the test.

    Args:
        request: The pytest request object.
        mocker: The pytest mocker object.

    Yields:
        control to the test function.
    """
    spy = mocker.spy(reflex.app.console, "error")
    yield
    if "ignore_console_error" not in request.keywords:
        spy.assert_not_called()
