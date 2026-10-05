"""Minimal pure-reflex repro: a user-defined State metaclass derived from the
public reflex.vars.BaseStateMeta can no longer be used on an rx.State subclass.

Usage: python repro_statemeta.py <venv-marker>   (run from a neutral cwd)
"""

import os
import sys

os.environ["REFLEX_TELEMETRY_ENABLED"] = "false"

import reflex as rx  # noqa: E402

assert sys.argv[1] in rx.__file__, rx.__file__
import importlib.metadata as im  # noqa: E402

print("reflex", im.version("reflex"), rx.__file__)

from reflex.vars import BaseStateMeta  # noqa: E402

print("type(rx.State) =", type(rx.State).__module__ + "." + type(rx.State).__name__)
print("BaseStateMeta  =", BaseStateMeta.__module__ + "." + BaseStateMeta.__name__)
print("is subclass ok =", issubclass(type(rx.State), BaseStateMeta))
print("meta usable    =", type(rx.State) is BaseStateMeta)


class MyStateMeta(BaseStateMeta):
    """A user-defined state metaclass, as reflex-enterprise 0.9.5 writes one."""

    def __new__(cls, name, bases, attrs, **kwargs):
        """Inject a field on every concrete subclass."""
        if not kwargs.get("mixin"):
            attrs.setdefault("__annotations__", {})["injected"] = str
            attrs["injected"] = "hello"
        return super().__new__(cls, name, bases, attrs, **kwargs)


try:

    class MyState(rx.State, metaclass=MyStateMeta):
        """A state using the custom metaclass."""

        n: int = 0

    print("RESULT PASS  class created; injected =", MyState.injected)
except TypeError as e:
    print("RESULT FAIL  TypeError:", e)
    sys.exit(1)
