"""Test misc utilities."""

import asyncio
import time

import pytest

from reflex.utils.misc import run_in_thread


async def test_run_in_thread():
    """Test that run_in_thread runs a function in a separate thread."""

    def simple_function():
        return 42

    result = await run_in_thread(simple_function)
    assert result == 42

    def slow_function():
        time.sleep(0.1)
        return "completed"

    result = await run_in_thread(slow_function, timeout=0.5)
    assert result == "completed"

    async def async_function():
        return 42

    with pytest.raises(ValueError):
        await run_in_thread(async_function)


async def test_run_in_thread_timeout():
    """Test that run_in_thread raises TimeoutError when timeout is exceeded."""

    def very_slow_function():
        time.sleep(0.5)
        return "should not reach here"

    with pytest.raises(asyncio.TimeoutError):
        await run_in_thread(very_slow_function, timeout=0.1)
