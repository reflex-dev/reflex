import asyncio
import contextlib
from unittest.mock import Mock

import pytest

from reflex.utils.tasks import ensure_task


class NotSuppressedError(Exception):
    """An exception that should not be suppressed."""


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
    """Test that ensure_task raises after exceeding exception limit within the limit window."""
    call_count = 0

    async def faulty_coro():
        nonlocal call_count
        call_count += 1
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
        exception_limit=3,
        exception_limit_window=0.1,
    )

    with contextlib.suppress(asyncio.CancelledError), pytest.raises(RuntimeError):
        await asyncio.wait_for(owner.task, timeout=3)

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
