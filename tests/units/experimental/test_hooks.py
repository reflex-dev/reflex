"""Tests for the experimental React hook wrappers."""

from collections.abc import Callable
from typing import Any

import pytest
from reflex_base.utils.exceptions import BackendVarFormatError

from reflex.experimental.hooks import const, useCallback, useContext, useRef, useState
from reflex.state import BaseState


class HooksState(BaseState):
    """A state with a backend var."""

    _secret: str = "x"


@pytest.mark.parametrize(
    "hook",
    [
        lambda f: const("value", f),
        lambda f: useCallback(f, []),
        useContext,
        useRef,
        lambda f: useState("value", f),
    ],
    ids=["const", "useCallback", "useContext", "useRef", "useState"],
)
def test_hook_backend_var_raises_format_error(hook: Callable[[Any], Any]):
    """A backend var passed to a hook raises instead of putting its repr in JS.

    Args:
        hook: Calls a hook with the backend var.
    """
    with pytest.raises(
        BackendVarFormatError, match=r"Backend var 'HooksState\._secret' exists only"
    ):
        hook(HooksState._secret)
