"""A3-01 repros converted to the supported a4 API (patch the FIELD). Each case_* is followed by a check_* test asserting
the configured default (10) is back for later tests.

Run: EXPECT_VENV=$NEW $SB/envs/$NEW/bin/python -I -m pytest -p no:cacheprovider -p no:randomly -rA -q -s test_converted_attr.py
"""

import os
import pickle
from unittest import mock

import pytest

import reflex as rx

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__


class Other(rx.State):
    y: int = 1


class Svc(rx.State):
    limit: int = 0
    _quota: int = 0
    items: list[str] = []
    theme: str = rx.LocalStorage("light", name="svc_theme", sync=True)


class SvcChild(Svc):
    extra: int = 0


# app-level configuration, the supported way (base_vars.md "Changing Defaults")
Svc.__fields__["limit"].default = 10
Svc.__fields__["_quota"].default = 10
Svc.__fields__["items"].default_factory = lambda: ["a"]


def fresh(cls=Svc):
    s = cls(_reflex_internal_init=True)
    return s.limit, s._quota, list(s.items)


CONFIGURED = (10, 10, ["a"])


def test_configured_at_import():
    assert fresh() == CONFIGURED
    s = Svc(_reflex_internal_init=True)
    s.limit, s._quota = 1, 2
    s.items.append("b")
    s.reset()
    assert (s.limit, s._quota, list(s.items)) == CONFIGURED  # reset() uses the configured default
    s.items.append("c")
    assert fresh() == CONFIGURED  # default_factory builds a new list per instance
    s3 = pickle.loads(pickle.dumps(s))
    assert list(s3.items) == ["a", "c"]
    assert fresh(SvcChild) == CONFIGURED  # inherited var: the declaring state's field


# controls
def test_case_ctrl_monkeypatch(monkeypatch):
    monkeypatch.setattr(Svc.__fields__["limit"], "default", 99)
    assert fresh()[0] == 99
    assert fresh(SvcChild)[0] == 99


def test_check_ctrl_monkeypatch():
    assert fresh() == CONFIGURED


def test_case_ctrl_mock():
    with mock.patch.object(Svc.__fields__["_quota"], "default", 7):
        assert fresh()[1] == 7
    assert fresh() == CONFIGURED


def test_case_ctrl_nested(monkeypatch):
    monkeypatch.setattr(Svc.__fields__["limit"], "default", 20)
    with mock.patch.object(Svc.__fields__["limit"], "default", 30):
        assert fresh()[0] == 30
    assert fresh()[0] == 20


def test_check_ctrl_nested():
    assert fresh() == CONFIGURED


# (a) the original patched a Var in: the field does not validate (documented), so a Var default is accepted during the window
def test_case_a_mock_var():
    with mock.patch.object(Svc.__fields__["limit"], "default", Other.y):
        v = fresh()[0]
        print(f"\n(a) field default patched with a Var: instance reads {type(v).__name__} {v!s}")


def test_check_a():
    assert fresh() == CONFIGURED


# (b) mocker with a value
def test_case_b_mocker(mocker):
    mocker.patch.object(Svc.__fields__["_quota"], "default", 5)
    assert fresh()[1] == 5


def test_check_b():
    assert fresh() == CONFIGURED


# (c) code under test reconfigures the field default inside the patch window
def test_case_c_assign_inside_window(monkeypatch):
    monkeypatch.setattr(Svc.__fields__["limit"], "default", 99)
    Svc.__fields__["limit"].default = 50  # configure() helper under test
    assert fresh()[0] == 50


def test_check_c():
    assert fresh() == CONFIGURED  # plain attribute semantics: monkeypatch puts back what it saved


# (d) PR #7516 recipe: monkeypatch.delattr + monkeypatch.setattr(raising=False) on the declaring class
def test_case_d_delattr_then_setattr(monkeypatch):
    monkeypatch.delattr(Svc, "_quota")
    monkeypatch.setattr(Svc, "_quota", 77, raising=False)
    s = Svc(_reflex_internal_init=True)
    print(f"\n(d) delattr+setattr(77): Svc._quota={Svc._quota!r} instance._quota={s._quota!r} "
          f"field default={Svc.__fields__['_quota'].default!r}")
    s._quota = 5
    print(f"(d) after instance write: instance._quota={s._quota!r} dirty={getattr(s, 'dirty_vars', None)}")


def test_check_d():
    assert fresh() == CONFIGURED
    assert type(Svc.__dict__["_quota"]).__name__ == "Field"
    assert Svc.__dict__["_quota"] is Svc.__fields__["_quota"]


# default_factory patching (mutable)
def test_case_factory(monkeypatch):
    monkeypatch.setattr(Svc.__fields__["items"], "default_factory", lambda: ["p"])
    assert fresh()[2] == ["p"]


def test_check_factory():
    assert fresh() == CONFIGURED


# patching `default` on a var whose default is MISSING (mutable): default wins over the factory while patched, then MISSING again
def test_case_default_over_factory():
    f = Svc.__fields__["items"]
    with mock.patch.object(f, "default", ["shared"]):
        a, b = Svc(_reflex_internal_init=True), Svc(_reflex_internal_init=True)
        print(f"\ndefault over factory: a.items={list(a.items)} same object={a.__dict__.get('items') is b.__dict__.get('items')}")
    print(f"after: default={f.default!r} factory={f.default_factory}")


def test_check_default_over_factory():
    assert fresh() == CONFIGURED


# patching through a substate's __fields__ reaches the declaring state's field (shared object)
def test_case_substate_field(monkeypatch):
    assert SvcChild.__fields__["limit"] is Svc.__fields__["limit"]
    monkeypatch.setattr(SvcChild.__fields__["limit"], "default", 3)
    assert fresh()[0] == 3 and fresh(SvcChild)[0] == 3


def test_check_substate_field():
    assert fresh() == CONFIGURED and fresh(SvcChild) == CONFIGURED


# storage var: patch with a storage value keeps storage; patch with a plain str (documented) loses name/options
def _storage_entry(cls, name):
    from reflex.compiler.utils import _compile_client_storage_recursive

    for kind, d in zip(("cookie", "local", "session"), _compile_client_storage_recursive(cls)):
        for k, v in d.items():
            if k.rsplit(".", 1)[-1].split("_rx_state_")[0] == name:
                return kind, v
    return None


def test_case_storage_field_patch():
    f = Svc.__fields__["theme"]
    before = _storage_entry(Svc, "theme")
    with mock.patch.object(f, "default", rx.LocalStorage("dark", name="svc_theme2", sync=True)):
        during = _storage_entry(Svc, "theme")
    with mock.patch.object(f, "default", "plain"):
        plain = _storage_entry(Svc, "theme")
    after = _storage_entry(Svc, "theme")
    print(f"\nstorage before={before}\n  during(storage value)={during}\n  during(plain str)={plain}\n  after={after}")
    assert before == after and during[1]["name"] == "svc_theme2" and plain is None
