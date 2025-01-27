"""Shared conftest for all integration tests."""

import os

import pytest

import reflex.app
from reflex.config import environment
from reflex.testing import AppHarness, AppHarnessProd

DISPLAY = None
XVFB_DIMENSIONS = (800, 600)


@pytest.fixture(scope="session", autouse=True)
def xvfb():
    """Create virtual X display.

    This function is a no-op unless GITHUB_ACTIONS is set in the environment.

    Yields:
        the pyvirtualdisplay object that the browser will be open on
    """
    if os.environ.get("GITHUB_ACTIONS") and not environment.APP_HARNESS_HEADLESS.get():
        from pyvirtualdisplay.smartdisplay import (  # pyright: ignore [reportMissingImports]
            SmartDisplay,
        )

        global DISPLAY
        with SmartDisplay(visible=False, size=XVFB_DIMENSIONS) as DISPLAY:
            yield DISPLAY
        DISPLAY = None
    else:
        yield None


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
def raise_console_error(request, mocker):
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
