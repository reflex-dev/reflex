"""Realistic State *method* patching patterns seen in public Reflex repos (kern-mrp, mex-consent, flexgen, mailarc).

These should keep working on 0.10.0a2 (control group for T-1).
"""
import asyncio
import os
from unittest import mock
from unittest.mock import AsyncMock, MagicMock

import pytest
import reflex as rx

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__


def inst(cls):
    try:
        return cls(_reflex_internal_init=True)
    except TypeError:
        return cls()


class AppState(rx.State):
    status: str = ""
    _failed_msgs: list[str] = []

    async def _actor(self) -> str:
        return "real-actor"

    def _route_param(self, key: str) -> str:
        return "real-" + key

    def _failed(self, msg: str) -> None:
        self._failed_msgs.append(msg)

    async def whoami(self) -> str:
        return await self._actor()


def test_patch_object_private_async_method_with_asyncmock():
    s = inst(AppState)
    with mock.patch.object(AppState, "_actor", AsyncMock(return_value="A")):
        assert asyncio.run(s._actor()) == "A"
    assert asyncio.run(inst(AppState)._actor()) == "real-actor"


def test_patch_object_private_method_with_side_effect():
    with mock.patch.object(AppState, "_route_param", side_effect=lambda key: "101" if key == "record_id" else "x"):
        s = inst(AppState)
        assert s._route_param("record_id") == "101"
    assert inst(AppState)._route_param("k") == "real-k"


def test_monkeypatch_setattr_private_method_with_plain_function(monkeypatch):
    recorded = []
    monkeypatch.setattr(AppState, "_failed", lambda self, msg: recorded.append(msg))
    inst(AppState)._failed("boom")
    assert recorded == ["boom"]


def test_monkeypatch_mark_dirty_with_spec_mock(monkeypatch):
    monkeypatch.setattr(AppState, "_mark_dirty", MagicMock(spec=AppState._mark_dirty))
    s = inst(AppState)
    s.status = "x"  # goes through Field.__set__ -> _mark_dirty on the (patched) class


def test_after_patches_everything_is_restored():
    assert asyncio.run(inst(AppState)._actor()) == "real-actor"
    assert inst(AppState)._route_param("k") == "real-k"
    assert AppState._mark_dirty is not None and not isinstance(AppState._mark_dirty, MagicMock)
