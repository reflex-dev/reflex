"""Tests for reflex.utils.cli_options."""

import os

import click
from reflex_base.constants import LogLevel
from reflex_base.utils import log

from reflex.utils import cli_options


def test_set_loglevel_flag_equal_to_current_level_still_exports_env(monkeypatch):
    """An explicit --loglevel flag reaches REFLEX_LOGLEVEL even when unchanged."""
    monkeypatch.delenv("REFLEX_LOGLEVEL", raising=False)
    monkeypatch.setattr(log, "_log_level", LogLevel.INFO)
    ctx = click.Context(click.Command("reflex"))
    param = click.Option(["--loglevel"])

    cli_options.set_loglevel(ctx, param, "info")

    assert os.environ.get("REFLEX_LOGLEVEL") == "info"
    assert log.get_log_level() is LogLevel.INFO
