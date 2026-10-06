"""Tests for the reflex package entry point."""

from __future__ import annotations

import importlib
import logging
import sys
from typing import NamedTuple

import pytest
from reflex_base.utils import log

import reflex


class _VersionInfo(NamedTuple):
    """A stand-in for ``sys.version_info``, which cannot be instantiated."""

    major: int
    minor: int
    micro: int = 0
    releaselevel: str = "final"
    serial: int = 0


@pytest.mark.parametrize(
    ("version", "deprecated"),
    [(_VersionInfo(3, 10, 12), True), (_VersionInfo(3, 11), False)],
    ids=["3.10", "3.11"],
)
def test_import_deprecates_python_310(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    version: _VersionInfo,
    deprecated: bool,
):
    """Importing reflex on Python 3.10 warns that support ends in 0.11.0.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        caplog: The pytest log capture fixture.
        version: The interpreter version to import under.
        deprecated: Whether that version is deprecated.
    """
    # The suite's own import may already have claimed the dedupe key on 3.10.
    log._dedupe_filter().seen.clear()
    monkeypatch.setattr(sys, "version_info", version)

    with caplog.at_level(logging.WARNING, logger="reflex.deprecation"):
        importlib.reload(reflex)

    messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "reflex.deprecation"
    ]
    if not deprecated:
        assert messages == []
        return
    assert len(messages) == 1
    message = messages[0]
    assert "Support for Python 3.10 has been deprecated in version 0.10.0" in message
    assert "Upgrade to Python 3.11 or newer" in message
    assert "removed in 0.11.0" in message
