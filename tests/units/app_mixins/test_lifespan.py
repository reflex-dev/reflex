"""Unit tests for lifespan app mixin behavior."""

from __future__ import annotations

import functools

from reflex.app_mixins.lifespan import LifespanMixin


def test_register_lifespan_task_can_be_used_as_decorator():
    """Decorating a task registers it and preserves the task callable."""
    mixin = LifespanMixin()

    @mixin.register_lifespan_task
    def polling_task() -> str:
        """Return a sentinel value for direct-call verification.

        Returns:
            A sentinel string.
        """
        return "ok"

    assert polling_task() == "ok"
    assert polling_task in mixin.get_lifespan_tasks()


def test_register_lifespan_task_with_kwargs_can_be_used_as_decorator():
    """Decorator-with-kwargs preserves function binding and registers partial."""
    mixin = LifespanMixin()

    @mixin.register_lifespan_task(timeout=10)
    def check_for_updates(timeout: int) -> int:
        """Echo timeout to verify direct function access is preserved.

        Args:
            timeout: Timeout value in seconds.

        Returns:
            The timeout value passed to the function.
        """
        return timeout

    assert check_for_updates(timeout=4) == 4

    registered_tasks = mixin.get_lifespan_tasks()
    assert len(registered_tasks) == 1
    registered_task = registered_tasks[0]
    assert isinstance(registered_task, functools.partial)
    assert registered_task.func is check_for_updates
    assert registered_task.keywords == {"timeout": 10}
