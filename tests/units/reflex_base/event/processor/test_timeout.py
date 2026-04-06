"""Tests for DrainTimeoutManager."""

import time

from reflex_base.event.processor.timeout import DrainTimeoutManager


def test_drain_timeout_no_timeout():
    """DrainTimeoutManager with no timeout returns 0."""
    dtm = DrainTimeoutManager.with_timeout(None)
    with dtm as remaining:
        assert remaining == 0


def test_drain_timeout_decreases():
    """DrainTimeoutManager remaining time decreases across re-entries."""
    dtm = DrainTimeoutManager.with_timeout(10.0)
    with dtm as first:
        assert 9.5 < first <= 10.0
    time.sleep(0.1)
    with dtm as second:
        assert second < first


def test_drain_timeout_expired_returns_zero():
    """DrainTimeoutManager with an already-expired timeout returns 0."""
    dtm = DrainTimeoutManager.with_timeout(0)
    with dtm as remaining:
        assert remaining == 0
