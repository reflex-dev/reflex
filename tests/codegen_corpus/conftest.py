"""Corpus-wide pytest configuration."""

from __future__ import annotations

import pytest


def pytest_collection_modifyitems(config, items):  # noqa: ARG001
    """Skip the corpus suite when the Rust wheel isn't installed.

    The corpus tests would otherwise emit confusing import errors at
    collection. We let pytest skip cleanly at the test level via the
    ``rust_required`` marker applied below.
    """
    try:
        from reflex_compiler_rust import _native  # noqa: F401
    except ImportError:
        skip = pytest.mark.skip(reason="reflex_compiler_rust wheel not installed")
        for item in items:
            item.add_marker(skip)
