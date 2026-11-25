"""Tests for the shared click options of the reflex CLI."""

import os

import click
import pytest
from click.testing import CliRunner
from reflex_base.config import Config
from reflex_base.constants import LogLevel
from reflex_base.utils import log

from reflex.utils.cli_options import loglevel_option


@click.command()
@loglevel_option
def _loglevel_command():
    """Carry only the --loglevel option."""


@pytest.mark.parametrize(
    "rxconfig_loglevel",
    [LogLevel.DEFAULT, LogLevel.WARNING],
    ids=["rxconfig_default", "rxconfig_warning"],
)
def test_explicit_loglevel_is_honoured_when_level_is_unchanged(
    monkeypatch: pytest.MonkeyPatch, rxconfig_loglevel: LogLevel
):
    """An explicit --loglevel info reaches the config even when INFO is already the level.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        rxconfig_loglevel: The loglevel the app's rxconfig.py sets.
    """
    # Set before deleting so teardown also removes the value the CLI writes.
    monkeypatch.setenv("REFLEX_LOGLEVEL", "")
    monkeypatch.delenv("REFLEX_LOGLEVEL")
    monkeypatch.setattr(log, "_log_level", LogLevel.INFO)

    result = CliRunner().invoke(_loglevel_command, ["--loglevel", "info"])

    assert result.exit_code == 0
    env_loglevel = os.environ.get("REFLEX_LOGLEVEL")
    assert env_loglevel == "info"
    assert Config(app_name="demo", loglevel=rxconfig_loglevel).loglevel is LogLevel.INFO
    assert log.get_log_level() is LogLevel.INFO
