"""Fixtures for the hosting CLI command tests."""

import pytest
from reflex_base.utils import log


@pytest.fixture(autouse=True)
def _managed_logging(monkeypatch):
    """Run each CLI test with the managed logging sinks attached.

    The commands under test always execute under the ``reflex`` group in
    production, whose callback enables managed logging; invoking them
    directly through CliRunner skips that, so attach the sinks here to keep
    logger output visible in ``result.output``.
    """
    monkeypatch.setenv(log._MANAGED_ENV_VAR, "true")
    log.configure()
    yield
    log._reset()
