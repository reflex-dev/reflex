"""Cosmetic anomaly: mock.patch.object(Substate, "inherited_var", v).

Run: cd $W/patchprobe && EXPECT_VENV=<venv> $SB/envs/<venv>/bin/python -I -m pytest -p no:cacheprovider -p no:randomly -q test_patch_substate.py
The two test_show_* tests FAIL on purpose so pytest prints what a user sees.
"""
import os
from unittest import mock

import reflex as rx

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__


class Parent(rx.State):
    limit: int = 10


class Child(Parent):
    other: int = 0


def chain(exc):
    out = []
    while exc is not None:
        out.append(f"{type(exc).__name__}: {exc}")
        exc = exc.__context__
    return out


def test_chain_on_substate():
    try:
        with mock.patch.object(Child, "limit", 99):
            pass
    except Exception as e:  # noqa: BLE001
        print("\nSUBSTATE CHAIN (outermost first):", *chain(e), sep="\n  ")
    else:
        print("\nSUBSTATE: no exception")
    print("after: Child.limit is Parent's field var:", getattr(Child.limit, "_js_expr", Child.limit))
    print("fresh instance:", Parent(_reflex_internal_init=True).substates[Child.get_name()].limit)


def test_chain_on_declaring_state():
    try:
        with mock.patch.object(Parent, "limit", 99):
            pass
    except Exception as e:  # noqa: BLE001
        print("\nDECLARING CHAIN (outermost first):", *chain(e), sep="\n  ")
    else:
        print("\nDECLARING: no exception")


def test_show_substate_patch():
    with mock.patch.object(Child, "limit", 99):
        pass


def test_show_substate_patch_decorator_form():
    @mock.patch.object(Child, "limit", 99)
    def inner():
        pass

    inner()
