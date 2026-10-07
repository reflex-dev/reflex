"""#7495 undo-stack edge cases in a real pytest run. Each *_patch test is followed by a sentinel that expects the
CONFIGURED default (10) to be back. Run: EXPECT_VENV=<venv> <venv>/bin/python -I -m pytest -p no:cacheprovider -p no:randomly -rA -q test_undo_edge.py
"""
import os
from unittest import mock

import pytest
import reflex as rx

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__


class Other(rx.State):
    y: int = 1


class Svc(rx.State):
    limit: int = 0
    _quota: int = 0


# app-level configuration of the defaults (documented #7461 usage)
Svc.limit = 10
Svc._quota = 10


def fresh(name):
    return getattr(Svc(_reflex_internal_init=True), name)


def test_a1_mock_patch_with_a_var_is_rejected():
    with pytest.raises(TypeError):
        with mock.patch.object(Svc, "limit", Other.y):
            pass


def test_a2_sentinel_limit_still_configured():
    assert fresh("limit") == 10


def test_b1_mocker_patch_with_a_field_is_rejected(mocker):
    with pytest.raises(TypeError):
        mocker.patch.object(Svc, "_quota", rx.field(5))


def test_b2_sentinel_quota_still_configured():
    assert fresh("_quota") == 10


def test_c1_patch_then_code_under_test_reconfigures(monkeypatch):
    monkeypatch.setattr(Svc, "limit", 99)
    Svc.limit = 50  # e.g. the code under test applies settings to the class
    assert fresh("limit") == 50


def test_c2_sentinel_limit_back_to_configured():
    assert fresh("limit") == 10


def test_d1_monkeypatch_delattr(monkeypatch):
    monkeypatch.delattr(Svc, "_quota")


def test_d2_sentinel_quota_back_to_configured():
    assert fresh("_quota") == 10
