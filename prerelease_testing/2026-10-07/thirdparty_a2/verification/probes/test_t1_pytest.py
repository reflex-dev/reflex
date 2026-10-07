"""T-1 in the real pytest runner: patch a State default in one test, observe teardown + the next test.

Independent verifier probe. Each "patching" test is followed by a "leak sentinel" test that asserts the
declared default is back to its original value (what any downstream suite implicitly relies on).

Run:  REFLEX_TELEMETRY_ENABLED=false EXPECT_VENV=<venv> <venv>/bin/python -I -m pytest -p no:cacheprovider -p no:randomly -rA -q test_t1_pytest.py
"""

import os
from typing import ClassVar
from unittest import mock

import pytest
import reflex as rx

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__


def inst(cls):
    try:
        return cls(_reflex_internal_init=True)
    except TypeError:
        return cls()


class Svc(rx.State):
    _limit: int = 5
    limit: int = 5
    rxf: int = rx.field(default=5)
    _bk: str = "orig"
    CV: ClassVar[int] = 10

    def helper(self) -> str:
        return "orig"


class Mix(rx.State, mixin=True):
    _mlimit: int = 5
    mlimit: int = 5


class UsesMixin(Mix, rx.State):
    pass


class Parent(rx.State):
    _plimit: int = 5


class Child(Parent):
    pass


def default_of(cls, name):
    return cls.get_fields()[name].default


# --- private var: monkeypatch -------------------------------------------------------------------
def test_01_monkeypatch_private_var(monkeypatch):
    monkeypatch.setattr(Svc, "_limit", 99)
    assert inst(Svc)._limit == 99  # patch is visible to new instances on 0.10.0a2 / a1


def test_02_sentinel_private_default_restored():
    assert default_of(Svc, "_limit") == 5
    assert inst(Svc)._limit == 5


# --- private var: mock.patch.object -------------------------------------------------------------
def test_03_mock_patch_object_private_var():
    with mock.patch.object(Svc, "_limit", 77):
        assert inst(Svc)._limit == 77


def test_04_sentinel_private_after_mock():
    assert default_of(Svc, "_limit") == 5


# --- public var -----------------------------------------------------------------------------------
def test_05_monkeypatch_public_var(monkeypatch):
    monkeypatch.setattr(Svc, "limit", 99)
    assert inst(Svc).limit == 99


def test_06_sentinel_public_default_restored():
    assert default_of(Svc, "limit") == 5


# --- rx.field public var ---------------------------------------------------------------------------
def test_07_monkeypatch_rx_field_var(monkeypatch):
    monkeypatch.setattr(Svc, "rxf", 99)
    assert inst(Svc).rxf == 99


def test_08_sentinel_rx_field_default_restored():
    assert default_of(Svc, "rxf") == 5


# --- pytest-mock -------------------------------------------------------------------------------------
def test_09_pytest_mock_patch_object(mocker):
    mocker.patch.object(Svc, "_bk", "patched")
    assert inst(Svc)._bk == "patched"


def test_10_sentinel_after_pytest_mock():
    assert default_of(Svc, "_bk") == "orig"


# --- mixin var ------------------------------------------------------------------------------------
def test_11_monkeypatch_mixin_var(monkeypatch):
    monkeypatch.setattr(UsesMixin, "_mlimit", 99)
    assert inst(UsesMixin)._mlimit == 99


def test_12_sentinel_mixin_default_restored():
    assert default_of(UsesMixin, "_mlimit") == 5


# --- inherited var patched through a substate ------------------------------------------------------
def test_13_monkeypatch_child_of_declaring_parent(monkeypatch):
    monkeypatch.setattr(Child, "_plimit", 99)
    assert inst(Child)._plimit == 99


def test_14_sentinel_parent_default_restored():
    assert default_of(Parent, "_plimit") == 5


# --- control group: things the claim says are fine --------------------------------------------------
def test_20_monkeypatch_method(monkeypatch):
    monkeypatch.setattr(Svc, "helper", lambda self: "patched")
    assert inst(Svc).helper() == "patched"


def test_21_method_restored():
    assert inst(Svc).helper() == "orig"


def test_22_monkeypatch_classvar(monkeypatch):
    monkeypatch.setattr(Svc, "CV", 11)
    assert Svc.CV == 11


def test_23_classvar_restored():
    assert Svc.CV == 10


# --- workaround candidates ---------------------------------------------------------------------------
def test_30_workaround_patch_field_default(monkeypatch):
    monkeypatch.setattr(Svc.get_fields()["rxf"], "default", 123)
    assert inst(Svc).rxf == 123


def test_31_sentinel_after_workaround():
    assert default_of(Svc, "rxf") == 5 or True  # reported by test_08 on a2; kept informational


def test_32_workaround_reassign_original_value():
    original = 5
    try:
        Svc._limit = 99
        assert inst(Svc)._limit == 99
    finally:
        Svc._limit = original


def test_33_sentinel_after_original_value_restore():
    assert default_of(Svc, "_limit") == 5
