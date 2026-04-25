"""Unit tests for integration test utilities."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from tests.integration import utils


class _FakePage:
    """Minimal page stub for testing poll_for_navigation."""

    def __init__(self) -> None:
        """Initialize fake page state."""
        self.url = "http://localhost:3000/"
        self.wait_calls: list[tuple[Callable[[str], bool], float]] = []

    def wait_for_url(self, predicate: Callable[[str], bool], timeout: float) -> None:
        """Record wait_for_url calls and validate the URL-change predicate.

        Args:
            predicate: URL-matcher callback passed by poll_for_navigation.
            timeout: Timeout in milliseconds.
        """
        self.wait_calls.append((predicate, timeout))
        assert not predicate("http://localhost:3000/")
        assert predicate("http://localhost:3000/next")


def test_poll_for_navigation_uses_playwright_wait_for_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """poll_for_navigation should delegate URL waiting to Playwright."""

    def _unexpected_expect(*_args: object, **_kwargs: object) -> None:
        msg = "poll_for_navigation should not call AppHarness.expect"
        raise AssertionError(msg)

    monkeypatch.setattr(utils.AppHarness, "expect", _unexpected_expect)

    page = _FakePage()
    with utils.poll_for_navigation(page, timeout=2.5):
        # The helper snapshots the current URL before yielding.
        pass

    assert len(page.wait_calls) == 1
    _, timeout_ms = page.wait_calls[0]
    assert timeout_ms == pytest.approx(2500.0)
