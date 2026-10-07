"""Verifier repro for a3_class_state-7: undo stack pops the latest entry, not the saved one.

Each case uses its own state class configured at import (`C.limit = 10`, `C._quota = 10`),
runs one patch pattern in a `case_*` test, then a `check_*` test (the next test in file order)
asserts that a fresh instance starts from the configured default 10 again.

Run: EXPECT_VENV=<venv-dir-name> <venv>/bin/python -I -m pytest -p no:cacheprovider -p no:randomly -rA -q test_v7_undo.py
"""

import os
from unittest import mock

import pytest

import reflex

assert f"/envs/{os.environ['EXPECT_VENV']}/" in reflex.__file__, reflex.__file__

import reflex as rx  # noqa: E402

VERSION = reflex.__file__.split("/envs/")[1].split("/")[0]


class Other(rx.State):
    y: int = 3


def _mk(tag):
    cls = type(f"Cfg_{tag}", (rx.State,), {"__module__": __name__, "__annotations__": {"limit": int, "_quota": int}, "limit": 0, "_quota": 0})
    cls.limit = 10
    cls._quota = 10
    return cls


def fresh(cls):
    s = cls(_reflex_internal_init=True)
    return s.limit, s._quota


CTRL_MP = _mk("ctrl_mp")
CTRL_MOCK = _mk("ctrl_mock")
CTRL_BADTYPE = _mk("ctrl_badtype")
CTRL_NESTED = _mk("ctrl_nested")
A_MOCK_VAR = _mk("a_mock_var")
A2_MP_VAR = _mk("a2_mp_var")
B_MOCKER_FIELD = _mk("b_mocker_field")
B2_MP_FIELD = _mk("b2_mp_field")
C_ASSIGN_IN_WINDOW = _mk("c_assign_in_window")
D_MP_DELATTR = _mk("d_mp_delattr")


# controls: these must pass on a3 (N-039 fix)
def test_case_ctrl_monkeypatch(monkeypatch):
    monkeypatch.setattr(CTRL_MP, "limit", 99)
    assert fresh(CTRL_MP) == (99, 10)


def test_check_ctrl_monkeypatch():
    assert fresh(CTRL_MP) == (10, 10)


def test_case_ctrl_mock_patch_object():
    with mock.patch.object(CTRL_MOCK, "_quota", 7):
        assert fresh(CTRL_MOCK) == (10, 7)


def test_check_ctrl_mock_patch_object():
    assert fresh(CTRL_MOCK) == (10, 10)


def test_case_ctrl_rejected_wrong_type():
    # A wrong-type value is rejected AFTER _keep_default is pushed: control for case (a).
    with pytest.raises(TypeError):
        with mock.patch.object(CTRL_BADTYPE, "limit", "not-an-int"):
            pass


def test_check_ctrl_rejected_wrong_type():
    assert fresh(CTRL_BADTYPE) == (10, 10)


def test_case_ctrl_nested(monkeypatch):
    monkeypatch.setattr(CTRL_NESTED, "limit", 20)
    with mock.patch.object(CTRL_NESTED, "limit", 30):
        assert fresh(CTRL_NESTED)[0] == 30
    assert fresh(CTRL_NESTED)[0] == 20


def test_check_ctrl_nested():
    assert fresh(CTRL_NESTED) == (10, 10)


# (a) rejected mock.patch.object with a Var value
def test_case_a_mock_patch_object_var():
    with pytest.raises(TypeError):
        with mock.patch.object(A_MOCK_VAR, "limit", Other.y):
            pass


def test_check_a_mock_patch_object_var():
    assert fresh(A_MOCK_VAR) == (10, 10)


# (a2) same, but with monkeypatch.setattr (not in the inbox: does monkeypatch hit it too?)
def test_case_a2_monkeypatch_var(monkeypatch):
    with pytest.raises(TypeError):
        monkeypatch.setattr(A2_MP_VAR, "limit", Other.y)


def test_check_a2_monkeypatch_var():
    assert fresh(A2_MP_VAR) == (10, 10)


# (b) rejected mocker.patch.object with an rx.field() value
def test_case_b_mocker_field(mocker):
    with pytest.raises(TypeError):
        mocker.patch.object(B_MOCKER_FIELD, "_quota", rx.field(5))


def test_check_b_mocker_field():
    assert fresh(B_MOCKER_FIELD) == (10, 10)


# (b2) monkeypatch.setattr with rx.field()
def test_case_b2_monkeypatch_field(monkeypatch):
    with pytest.raises(TypeError):
        monkeypatch.setattr(B2_MP_FIELD, "_quota", rx.field(5))


def test_check_b2_monkeypatch_field():
    assert fresh(B2_MP_FIELD) == (10, 10)


# (c) code under test assigns a default while a monkeypatch is active
def test_case_c_assign_inside_patch_window(monkeypatch):
    monkeypatch.setattr(C_ASSIGN_IN_WINDOW, "limit", 99)
    C_ASSIGN_IN_WINDOW.limit = 50  # e.g. a configure() helper the test exercises
    assert fresh(C_ASSIGN_IN_WINDOW)[0] == 50


def test_check_c_assign_inside_patch_window():
    # Plain-Python-attribute semantics would put back what monkeypatch saved (10).
    assert fresh(C_ASSIGN_IN_WINDOW) == (10, 10)


# (d) monkeypatch.delattr on a configured backend var
def test_case_d_monkeypatch_delattr(monkeypatch):
    monkeypatch.delattr(D_MP_DELATTR, "_quota")
    print(f"\n[{VERSION}] (d) during the test _quota starts at {fresh(D_MP_DELATTR)[1]}")


def test_check_d_monkeypatch_delattr():
    assert fresh(D_MP_DELATTR) == (10, 10)
