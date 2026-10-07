"""Reject framework imports outside the selected published environment."""

import os

import reflex
import reflex_otel

for module in (reflex, reflex_otel):
    assert f"/envs/{os.environ['REFLEX_TEST_ENV']}/" in module.__file__, module.__file__
