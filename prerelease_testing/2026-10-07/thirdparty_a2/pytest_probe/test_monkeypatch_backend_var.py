"""Downstream test-suite pattern: patch a class-level backend var for one test and restore it (pytest monkeypatch / mock.patch).

Run: <venv>/bin/python -m pytest -p no:cacheprovider -q test_monkeypatch_backend_var.py
"""
from unittest import mock

import reflex as rx


class Client:
    def __init__(self, name):
        self.name = name


class Svc(rx.State):
    _client: Client | None = None
    _limit: int = 5


def inst():
    root = rx.State(_reflex_internal_init=True)
    return root.get_substate(Svc.get_full_name().split(".")[1:])


def test_monkeypatch_setattr_value_of_declared_type(monkeypatch):
    monkeypatch.setattr(Svc, "_limit", 99)
    assert inst()._limit == 99


def test_after_monkeypatch_default_is_restored():
    assert inst()._limit == 5


def test_monkeypatch_setattr_mock(monkeypatch):
    monkeypatch.setattr(Svc, "_client", mock.Mock(name="fake"))
    assert inst()._client is not None


def test_mock_patch_object_context_manager():
    with mock.patch.object(Svc, "_limit", new=7):
        assert inst()._limit == 7
    assert inst()._limit == 5


@mock.patch.object(Svc, "_limit", 8)
def test_mock_patch_object_decorator():
    assert inst()._limit == 8


def test_after_all_default_is_restored():
    assert inst()._limit == 5
