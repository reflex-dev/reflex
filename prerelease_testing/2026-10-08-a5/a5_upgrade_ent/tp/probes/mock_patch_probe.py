"""Downstream test-suite patterns on class-level backend vars: unittest.mock.patch.object / pytest monkeypatch.

A package's own tests commonly replace a class-level backend attribute with a stub for the duration of a test and
restore it afterwards.  What does that do under the descriptor-based fields?

Usage: <venv>/bin/python mock_patch_probe.py <expected-venv-name>
"""
import pickle
import sys
from unittest import mock

import reflex as rx

assert f"/scratchpad/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__


class Client:
    def __init__(self, name):
        self.name = name


class Svc(rx.State):
    _client: Client | None = None
    _limit: int = 5
    _items: list[str] = []
    shown: str = ""


def inst():
    root = rx.State(_reflex_internal_init=True)
    return root.get_substate(Svc.get_full_name().split(".")[1:])


def show(label, fn):
    try:
        print(f"{label}: {fn()!r}"[:260])
    except BaseException as e:  # noqa: BLE001
        print(f"{label}: EXC {type(e).__name__}: {str(e)[:200]}")


show("baseline instance _client/_limit", lambda: (inst()._client, inst()._limit))
def step(label, fn):
    try:
        out = fn()
        print(f"{label}: {out!r}"[:300])
    except BaseException as e:  # noqa: BLE001
        print(f"{label}: EXC {type(e).__name__}: {str(e)[:170]}")


def cur_client():
    c = inst()._client
    return getattr(c, "name", c)


def dict_type(name):
    return type(Svc.__dict__[name]).__name__


# 1. plain class-level assignment of the declared type
step("1 class assign Client('real') -> instance", lambda: (setattr(Svc, "_client", Client("real")), cur_client())[1])

# 2. patch.object with a value of the declared type
def p2():
    with mock.patch.object(Svc, "_client", new=Client("patched")):
        during = cur_client()
    return f"during={during!r}"
step("2 patch.object(Svc, '_client', new=Client('patched')) (declared type)", p2)
step("2b after: instance _client / type in __dict__", lambda: (cur_client(), dict_type("_client")))

# 3. patch.object with a Mock (what test suites actually do)
def p3():
    with mock.patch.object(Svc, "_client", new=mock.Mock(name="fake")):
        during = type(inst()._client).__name__
    return f"during={during!r}"
step("3 patch.object(Svc, '_client', new=Mock())", p3)
step("3b after: instance _client / type in __dict__", lambda: (cur_client(), dict_type("_client")))

# 4. patch.object on an int var with an int
def p4():
    with mock.patch.object(Svc, "_limit", new=99):
        during = inst()._limit
    return f"during={during!r}"
step("4 patch.object(Svc, '_limit', new=99)", p4)
step("4b after: instance _limit / type in __dict__", lambda: (inst()._limit, dict_type("_limit")))

# 5. wrong type of plain value
step("5 class assign 'not-an-int' to an int var -> instance", lambda: (setattr(Svc, "_limit", "not-an-int"), inst()._limit)[1])
step("5b instance _limit afterwards", lambda: inst()._limit)

# 6. class-level mutation of a mutable default
step("6 Svc._items.append('x') at class level -> instance", lambda: (Svc._items.append("x"), inst()._items)[1])

# 7. patch.object(..., autospec/spec) of the whole attribute with a fresh Field-free object, then pickle
step("7 pickle round trip of instance", lambda: getattr(pickle.loads(pickle.dumps(inst()))._client, "name", None))
