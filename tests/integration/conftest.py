"""Shared conftest for all integration tests."""

import logging

import pytest

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
def raise_console_error(request):
    """Capture error-level log records emitted by the framework.

    Help catch spurious error conditions that might otherwise go unnoticed.

    If a test is marked with `ignore_console_error`, captured errors are
    ignored after the test.

    Args:
        request: The pytest request object.

    Yields:
        control to the test function.
    """

    class _ErrorCapture(logging.Handler):
        def __init__(self):
            super().__init__(level=logging.ERROR)
            self.records: list[logging.LogRecord] = []

        def emit(self, record: logging.LogRecord):
            self.records.append(record)

    capture = _ErrorCapture()
    # Handlers on a logger fire regardless of its propagate flag, and every
    # package logger chains through "reflex", so one attachment covers all.
    reflex_logger = logging.getLogger("reflex")
    reflex_logger.addHandler(capture)
    yield
    reflex_logger.removeHandler(capture)
    if "ignore_console_error" not in request.keywords:
        assert not capture.records, "\n".join(
            record.getMessage() for record in capture.records
        )
