"""Class-level assignment of a CALLABLE to a declared backend var (dependency-injection style: `State._send = send_email`).

a2 (#7461) treats a zero-argument callable that the field's annotation does not accept as a default FACTORY and calls it once
to validate.  What does that do to the callable patterns packages and apps actually use?

Usage: <venv>/bin/python callable_assign_probe.py <expected-venv-name>
"""
import functools
import sys
from typing import Any, Callable

import reflex as rx

assert f"/scratchpad/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__

CALLS = []


def hook():  # zero-arg, has a visible side effect
    CALLS.append("hook")
    return "hook-result"


def needs_arg(x):  # one required argument
    CALLS.append("needs_arg")
    return x


class Svc(rx.State):
    _untyped = None  # unannotated, default None
    _any: Any = None
    _typed: Callable[..., Any] | None = None
    _str: str = ""


def inst():
    root = rx.State(_reflex_internal_init=True)
    return root.get_substate(Svc.get_full_name().split(".")[1:])


def case(label, name, value):
    CALLS.clear()
    try:
        setattr(Svc, name, value)
        err = None
    except BaseException as e:  # noqa: BLE001
        err = f"EXC {type(e).__name__}: {str(e)[:110]}"
    got = inst()._typed if name == "_typed" else getattr(inst(), name)
    print(f"{label:58s} -> {err or 'assigned'} | called-during-assign={list(CALLS)} | instance reads {got!r}"[:330])


case("unannotated `_untyped = None`  <- zero-arg function", "_untyped", hook)
case("unannotated `_untyped = None`  <- 1-arg function", "_untyped", needs_arg)
case("unannotated `_untyped = None`  <- lambda x: x", "_untyped", lambda x: x)
case("unannotated `_untyped = None`  <- class (type)", "_untyped", dict)
case("`_any: Any = None`             <- zero-arg function", "_any", hook)
case("`_typed: Callable|None = None` <- zero-arg function", "_typed", hook)
case("`_typed: Callable|None = None` <- 1-arg function", "_typed", needs_arg)
case("`_typed: Callable|None = None` <- functools.partial", "_typed", functools.partial(needs_arg, 1))
case("`_str: str = ''`               <- zero-arg function", "_str", hook)
