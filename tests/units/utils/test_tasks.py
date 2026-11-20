import asyncio
import contextlib
import logging
from collections.abc import Callable
from typing import Any
from unittest.mock import Mock

import pytest

from reflex.utils.tasks import ensure_task


class NotSuppressedError(Exception):
    """An exception that should not be suppressed."""


@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Record the delays passed to asyncio.sleep instead of waiting for them.

    Args:
        monkeypatch: The pytest monkeypatch fixture.

    Returns:
        The recorded delays, in call order.
    """
    delays: list[float] = []
    real_sleep = asyncio.sleep

    async def sleep(delay: float) -> None:
        delays.append(delay)
        await real_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", sleep)
    return delays


def _task_logs(caplog: pytest.LogCaptureFixture) -> list[tuple[str, str]]:
    """Get the level and message of every record logged by reflex.utils.tasks.

    Args:
        caplog: The pytest log capture fixture.

    Returns:
        The (level name, message) pairs, in log order.
    """
    return [
        (record.levelname, record.getMessage())
        for record in caplog.records
        if record.name == "reflex.utils.tasks"
    ]


@pytest.mark.asyncio
async def test_ensure_task_suppresses_exceptions():
    """Test that ensure_task suppresses specified exceptions."""
    call_count = 0

    async def faulty_coro():  # noqa: RUF029
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("Intentional error")  # noqa: EM101
        if call_count > 4:
            raise NotSuppressedError("Should not be suppressed")  # noqa: EM101
        return "Success"

    # Use ensure_task to run the faulty_coro, suppressing ValueError
    owner = Mock()
    ensure_task(
        owner=owner,
        task_attribute="task",
        coro_function=faulty_coro,
        suppress_exceptions=[ValueError],
        exception_delay=0,
        exception_limit=5,
        exception_limit_window=1.0,
    )

    with contextlib.suppress(asyncio.CancelledError), pytest.raises(NotSuppressedError):
        await asyncio.wait_for(owner.task, timeout=1)

    # Should have retried until success, then raised RuntimeError
    assert call_count == 5


async def test_ensure_task_limit_window():
    """Test that ensure_task raises after exceeding exception limit within the limit window."""
    call_count = 0

    async def faulty_coro():  # noqa: RUF029
        nonlocal call_count
        call_count += 1
        raise ValueError("Intentional error")  # noqa: EM101

    owner = Mock()
    ensure_task(
        owner=owner,
        task_attribute="task",
        coro_function=faulty_coro,
        suppress_exceptions=[ValueError],
        exception_delay=0,
        exception_limit=3,
        exception_limit_window=1.0,
    )

    with contextlib.suppress(asyncio.CancelledError), pytest.raises(ValueError):
        await asyncio.wait_for(owner.task, timeout=1)

    # Should have raised after exceeding the limit
    assert call_count == 3


async def test_ensure_task_limit_window_passed():
    """Test that ensure_task resets exception limit past the limit window."""
    call_count = 0

    async def faulty_coro():
        nonlocal call_count
        call_count += 1
        # Sleep 50 ms, longer than the 10 ms limit window, to reset the count.
        await asyncio.sleep(0.05)
        if call_count > 3:
            raise RuntimeError("Test Passed")  # noqa: EM101
        raise ValueError("Should have been suppressed")  # noqa: EM101

    owner = Mock()
    ensure_task(
        owner=owner,
        task_attribute="task",
        coro_function=faulty_coro,
        suppress_exceptions=[ValueError],
        exception_delay=0,
        exception_limit=2,
        exception_limit_window=0.01,
    )

    with contextlib.suppress(asyncio.CancelledError), pytest.raises(RuntimeError):
        await asyncio.wait_for(owner.task, timeout=10)

    # Should have raised after exceeding the limit
    assert call_count == 4


def test_ensure_task_no_runtime_error_suppression():
    """Test that ensure_task raises if RuntimeError is in suppress_exceptions."""
    owner = Mock()

    with pytest.raises(RuntimeError, match="Cannot suppress RuntimeError"):
        ensure_task(
            owner=owner,
            task_attribute="task",
            coro_function=asyncio.sleep,
            suppress_exceptions=[RuntimeError],
            exception_delay=0,
            exception_limit=5,
            exception_limit_window=1.0,
        )


async def test_ensure_task_default_limit(
    sleeps: list[float], caplog: pytest.LogCaptureFixture
):
    """By default every error is logged and the task raises on the fifth within a minute.

    Args:
        sleeps: The recorded retry delays.
        caplog: The pytest log capture fixture.
    """
    call_count = 0

    async def faulty_coro():  # noqa: RUF029
        nonlocal call_count
        call_count += 1
        raise ValueError("Intentional error")  # noqa: EM101

    owner = Mock()
    ensure_task(
        owner=owner,
        task_attribute="task",
        coro_function=faulty_coro,
        suppress_exceptions=[ValueError],
    )

    with pytest.raises(ValueError) as exc_info:
        await asyncio.wait_for(owner.task, timeout=1)

    assert str(exc_info.value) == "Intentional error"
    assert call_count == 5
    assert sleeps == [1.0, 1.0, 1.0, 1.0]
    assert _task_logs(caplog) == [
        *[("ERROR", "faulty_coro: task error suppressed: Intentional error")] * 4,
        (
            "ERROR",
            "faulty_coro: task exceeded exception limit 5 within 60.0s: Intentional error",
        ),
    ]


@pytest.mark.parametrize(
    ("delays", "expected_sleeps"),
    [
        ({}, [1.0, 2.0, 4.0, 8.0, 16.0, 30.0, 30.0, 1.0]),
        (
            {"exception_delay": 0.5, "exception_delay_max": 3.0},
            [0.5, 1.0, 2.0, 3.0, 3.0, 3.0, 3.0, 0.5],
        ),
        # A first delay above the cap is capped too, also after a recovery.
        ({"exception_delay": 10.0, "exception_delay_max": 3.0}, [3.0] * 8),
    ],
)
async def test_ensure_task_no_limit(
    delays: dict[str, Any],
    expected_sleeps: list[float],
    sleeps: list[float],
    caplog: pytest.LogCaptureFixture,
):
    """Without a limit the task backs off up to the cap and logs state changes only.

    Args:
        delays: The delay arguments passed to ensure_task.
        expected_sleeps: The retry delays the task should wait for.
        sleeps: The recorded retry delays.
        caplog: The pytest log capture fixture.
    """
    caplog.set_level(logging.INFO, logger="reflex.utils.tasks")
    call_count = 0

    async def flaky_coro(recovered: Callable[[], None]):  # noqa: RUF029
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Nothing has failed yet, so there is no recovery to log.
            recovered()
        if call_count <= 7:
            msg = f"down {call_count}"
            raise ValueError(msg)
        recovered()
        if call_count == 8:
            raise ValueError("down again")  # noqa: EM101
        # A second call within the same run logs nothing.
        recovered()
        raise RuntimeError("Test Passed")  # noqa: EM101

    owner = Mock()
    ensure_task(
        owner=owner,
        task_attribute="task",
        coro_function=flaky_coro,
        suppress_exceptions=[ValueError],
        exception_limit=None,
        # There is no window without a limit: an elapsed one does not end a run of errors.
        exception_limit_window=0,
        **delays,
    )

    with pytest.raises(RuntimeError) as exc_info:
        await asyncio.wait_for(owner.task, timeout=1)

    assert str(exc_info.value) == "Test Passed"
    assert call_count == 9
    assert sleeps == expected_sleeps
    assert _task_logs(caplog) == [
        ("ERROR", "flaky_coro: task error, retrying until it recovers: down 1"),
        ("INFO", "flaky_coro: task recovered"),
        ("ERROR", "flaky_coro: task error, retrying until it recovers: down again"),
        ("INFO", "flaky_coro: task recovered"),
    ]


async def test_ensure_task_no_limit_cancel_during_retry_delay():
    """Cancelling a task that is waiting to retry ends it without waiting out the delay."""
    failed = asyncio.Event()

    async def faulty_coro(recovered: Callable[[], None]):  # noqa: RUF029
        failed.set()
        raise ValueError("Intentional error")  # noqa: EM101

    owner = Mock()
    task = ensure_task(
        owner=owner,
        task_attribute="task",
        coro_function=faulty_coro,
        suppress_exceptions=[ValueError],
        exception_delay=30.0,
        exception_limit=None,
    )
    await asyncio.wait_for(failed.wait(), timeout=1)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=1)

    assert task.cancelled()
