"""This module will provide interfaces for the state."""

import pickle
import sys
from collections.abc import Callable
from typing import Any

# Errors caught during pickling of state
HANDLED_PICKLE_ERRORS = (
    pickle.PicklingError,
    AttributeError,
    IndexError,
    TypeError,
    ValueError,
)


def _is_picklable(obj: Any, dumps: Callable[[object], bytes]) -> bool:
    try:
        dumps(obj)
    except Exception:
        return False
    else:
        return True


def debug_failed_pickles(obj: object, dumps: Callable[[object], bytes]):
    """Recursively check the picklability of an object and its contents.

    Args:
        obj: The object to check.
        dumps: The pickle dump function to use.

    Raises:
        HANDLED_PICKLE_ERRORS: If the object or any of its contents are not picklable.
    """
    if _is_picklable(obj, dumps):
        return
    if sys.version_info < (3, 11):
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            try:
                debug_failed_pickles(v, dumps)
            except HANDLED_PICKLE_ERRORS as e:
                e.add_note(f"While pickling dict value for key {k!r}")
                raise
            try:
                debug_failed_pickles(k, dumps)
            except HANDLED_PICKLE_ERRORS as e:
                e.add_note(f"While pickling dict key {k!r}")
                raise
        return
    if isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            try:
                debug_failed_pickles(v, dumps)
            except HANDLED_PICKLE_ERRORS as e:  # noqa: PERF203
                e.add_note(f"While pickling index {i} of {type(obj).__name__}")
                raise
        return
    picklable_thing = obj.__getstate__()
    if picklable_thing is not None:
        debug_failed_pickles(picklable_thing, dumps)
    else:
        try:
            dumps(obj)
        except HANDLED_PICKLE_ERRORS as e:
            e.add_note(f"While pickling object of type {type(obj).__name__}")
            raise
