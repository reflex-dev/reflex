"""Same downstream pattern for the OTHER kinds of state attributes: public var, computed var, event handler, plain method, ClassVar.

Each test patches the attribute on the class with pytest's monkeypatch / mock.patch.object and checks the original is back afterwards.
"""
from typing import ClassVar
from unittest import mock

import reflex as rx


class Svc2(rx.State):
    count: int = 1
    K: ClassVar[int] = 3

    @rx.var
    def doubled(self) -> int:
        return self.count * 2

    @rx.event
    def bump(self):
        self.count += 1

    def helper(self) -> str:
        return "real-helper"


def inst():
    root = rx.State(_reflex_internal_init=True)
    return root.get_substate(Svc2.get_full_name().split(".")[1:])


def test_patch_public_var_default(monkeypatch):
    monkeypatch.setattr(Svc2, "count", 41)
    assert inst().count == 41


def test_public_var_restored():
    assert inst().count == 1


def test_patch_plain_method(monkeypatch):
    monkeypatch.setattr(Svc2, "helper", lambda self: "fake")
    assert inst().helper() == "fake"


def test_plain_method_restored():
    assert inst().helper() == "real-helper"


def test_patch_event_handler_fn(monkeypatch):
    called = []
    monkeypatch.setattr(Svc2, "bump", lambda self: called.append(1))
    inst().bump()
    assert called


def test_event_handler_restored():
    assert Svc2.event_handlers["bump"].fn.__name__ == "bump"
    s = inst()
    s.bump.fn(s) if hasattr(s.bump, "fn") else s.bump()
    assert s.count == 2


def test_patch_computed_var(monkeypatch):
    monkeypatch.setattr(Svc2, "doubled", property(lambda self: 1234))
    assert inst().doubled == 1234


def test_computed_var_restored():
    assert inst().doubled == 2


def test_patch_classvar(monkeypatch):
    monkeypatch.setattr(Svc2, "K", 9)
    assert inst().K == 9


def test_classvar_restored():
    assert Svc2.K == 3 and inst().K == 3
