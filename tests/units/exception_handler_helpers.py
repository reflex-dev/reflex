"""Decorators for the exception handler annotation tests.

The decorator lives in its own module on purpose: ``functools.wraps`` copies the
annotations of the wrapped function onto the wrapper but keeps the wrapper's
``__globals__``, so a handler decorated here has to resolve its annotations in
the module where it was defined, not in this one.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any


def logged(fn: Callable) -> Callable:
    """Wrap a handler the way a logging decorator would.

    Args:
        fn: The handler to wrap.

    Returns:
        A wrapper that copies the handler's name and annotations.
    """

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return fn(*args, **kwargs)

    return wrapper
