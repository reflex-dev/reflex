"""Unit tests for integration test utilities."""

from __future__ import annotations

from typing import cast
from unittest.mock import Mock

import pytest
from playwright.sync_api import Page

from tests.integration import utils


def test_poll_for_navigation_uses_playwright_wait_for_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """poll_for_navigation should delegate URL waiting to Playwright."""

    def _unexpected_expect(*_args: object, **_kwargs: object) -> None:
        msg = "poll_for_navigation should not call AppHarness.expect"
        raise AssertionError(msg)

    monkeypatch.setattr(utils.AppHarness, "expect", _unexpected_expect)

    page_mock = Mock(spec=Page)
    page_mock.evaluate.return_value = "http://localhost:3000/"
    page = cast(Page, page_mock)

    with utils.poll_for_navigation(page, timeout=2.5):
        # The helper snapshots the current URL before yielding.
        pass

    page_mock.evaluate.assert_called_once_with("window.location.href")
    page_mock.wait_for_url.assert_called_once()

    predicate = page_mock.wait_for_url.call_args.args[0]
    timeout_ms = page_mock.wait_for_url.call_args.kwargs["timeout"]
    assert callable(predicate)
    assert not predicate("http://localhost:3000/")
    assert predicate("http://localhost:3000/next")
    assert timeout_ms == pytest.approx(2500.0)
