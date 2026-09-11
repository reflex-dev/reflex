"""Shared fixtures. Each test module owns exactly one harness (module scope), so
only one server is alive at a time while all modules run in ONE pytest process.
"""

from __future__ import annotations

import json
import os
from collections.abc import Generator
from pathlib import Path

import pytest

RESULTS = Path(os.environ.get("TA_RESULTS", "/tmp/ta_results.json"))
_collected: dict = {}


def record(key: str, value) -> None:
    _collected[key] = value
    RESULTS.write_text(json.dumps(_collected, indent=2, default=str))


@pytest.fixture(scope="session", autouse=True)
def _reset_results() -> Generator[None, None, None]:
    RESULTS.write_text("{}")
    yield
