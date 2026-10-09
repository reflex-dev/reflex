"""Finding 1, test-suite variant: patching the module-level default container with mock.patch.dict / monkeypatch.setitem.

Run: EXPECT_VENV=<venv> $SB/envs/<venv>/bin/python -I probe_patchdict.py
"""
import os
from unittest import mock

import reflex as rx

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402

DEFAULT_FILTERS = {"status": "open"}
FEATURES: list[str] = ["base"]


class Dash(rx.State):
    filters: dict[str, str] = DEFAULT_FILTERS
    _features: list[str] = FEATURES


with mock.patch.dict(DEFAULT_FILTERS, {"status": "closed"}):
    FEATURES.append("beta")  # e.g. a fixture enabling a feature flag
    s = Dash(_reflex_internal_init=True)
    print(f"reflex {version('reflex'):9} under mock.patch.dict -> filters={dict(s.filters)} _features={list(s._features)}")
    FEATURES.remove("beta")
