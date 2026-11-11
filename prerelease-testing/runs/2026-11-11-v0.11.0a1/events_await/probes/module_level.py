"""Module-level `@rx.event` functions (#7673 breaking / #7770 revert): what is registered, what warns, what breaks.

usage (neutral cwd): EXPECT_VENV=$SB/envs/new $SB/envs/new/bin/python -I module_level.py
"""
from __future__ import annotations

import contextlib
import io
import os
from typing import Optional

import reflex as rx

assert os.environ["EXPECT_VENV"] in rx.__file__, rx.__file__
from importlib.metadata import version

print("reflex", version("reflex"))


class S(rx.State):
    v: int = 0


class M(rx.State, mixin=True):
    w: int = 0


def case(label, make):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            f = make()
            res = f"-> {type(f).__name__}"
            if isinstance(f, rx.EventHandler):
                res += f" registered as {f.fn.__name__!r} on {f.state.__name__ if f.state else None}"
        except Exception as ex:
            res = f"RAISES {type(ex).__name__}: {str(ex)[:140]}"
    warn = " ".join(buf.getvalue().split())
    print(f"- {label:46s} {res}")
    if warn:
        print(f"    warning: {warn[:260]}")


def plain():
    @rx.event
    def helper(x: int) -> int:
        return x + 1

    return helper


def state_first():
    @rx.event
    def decentral(state: S, v: int):
        state.v = v

    return decentral


def state_str():
    @rx.event
    def decentral_str(state: "S", v: int):
        state.v = v

    return decentral_str


def state_unresolvable():
    @rx.event
    def decentral_fwd(state: "NotDefinedYet", v: int):  # noqa: F821
        state.v = v

    return decentral_fwd


def state_optional():
    @rx.event
    def decentral_opt(state: Optional[S], v: int):
        state.v = v

    return decentral_opt


def state_mixin():
    @rx.event
    def decentral_mixin(state: M, v: int):
        state.w = v

    return decentral_mixin


def state_unannotated():
    @rx.event
    def decentral_unannotated(state, v):
        state.v = v

    return decentral_unannotated


def no_params():
    @rx.event
    def nothing():
        return None

    return nothing


def a_lambda():
    return rx.event(lambda state: None)


def with_background():
    @rx.event(background=True)
    async def bg_helper(x: int) -> int:
        return x

    return bg_helper


def state_background():
    @rx.event(background=True)
    async def bg_decentral(state: S):
        async with state:
            state.v += 1

    return bg_decentral


def private_name():
    @rx.event
    def _private(state: S):
        pass

    return _private


for label, make in [
    ("plain helper (x: int)", plain),
    ("first param annotated with the state class", state_first),
    ('first param annotated "S" (string)', state_str),
    ("first param is an unresolvable forward ref", state_unresolvable),
    ("first param Optional[S]", state_optional),
    ("first param is a mixin state", state_mixin),
    ("unannotated params", state_unannotated),
    ("no params", no_params),
    ("lambda", a_lambda),
    ("background helper without state", with_background),
    ("background decentralized (state: S)", state_background),
    ("private name (_private)", private_name),
]:
    case(label, make)
