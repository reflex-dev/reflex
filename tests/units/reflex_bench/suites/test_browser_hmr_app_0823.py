"""Run browser.dev.ready and hmr.render.leaf for real against reflex 0.8.23 from PyPI.

``--reflex 0.8.23`` builds the subject's venv through ``subjects.resolve``, so
this downloads packages: ``REFLEX_BENCH_NETWORK_TESTS=1 uv run pytest
tests/units/reflex_bench/suites/test_browser_hmr_app_0823.py``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from reflex_bench import machine

from .test_browser_hmr_app import run_and_check

pytestmark = [
    pytest.mark.skipif(
        os.environ.get("REFLEX_BENCH_NETWORK_TESTS") != "1",
        reason="downloads reflex 0.8.23 and starts real apps; set REFLEX_BENCH_NETWORK_TESTS=1",
    ),
    pytest.mark.skipif(
        not machine._playwright_chromium(), reason="no Playwright chromium"
    ),
]


def test_browser_and_hot_reload_on_0_8_23(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    run_and_check(tmp_path, monkeypatch, "--reflex", "0.8.23")
