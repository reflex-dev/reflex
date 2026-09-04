"""Tests for the reflex CLI command tree."""

from __future__ import annotations

import importlib.metadata
from types import SimpleNamespace

import click
import click.testing
import pytest

from reflex import reflex
from reflex.reflex import _add_plugin_cli_commands, cli


def test_cloud_commands_registered():
    """The hosting CLI is installed, so the real commands are registered."""
    from reflex_cli.v2.deploy import deploy

    assert reflex.cli.commands["deploy"] is deploy
    assert isinstance(reflex.cli.commands["cloud"], click.Command)


def test_missing_command_reports_the_package(caplog: pytest.LogCaptureFixture):
    """Without the hosting CLI, the command says which package to install."""
    result = click.testing.CliRunner().invoke(reflex._missing_command("deploy"))

    assert result.exit_code == 1
    assert "is not installed" in caplog.text
    assert "pip install reflex-hosting-cli" in caplog.text


def test_missing_command_tolerates_flags(caplog: pytest.LogCaptureFixture):
    """The stand-in reports the missing package instead of a usage error.

    The real command's flags must not produce "No such option", which would hide
    the actual cause from the user.
    """
    result = click.testing.CliRunner().invoke(
        reflex._missing_command("deploy"), ["--app-name", "demo", "--no-interactive"]
    )

    assert result.exit_code == 1
    assert "pip install reflex-hosting-cli" in caplog.text
    assert "No such option" not in result.output


@click.command()
def _fake_command():
    """A plugin-contributed command."""


def _entry_point(name: str) -> SimpleNamespace:
    return SimpleNamespace(
        name=name, value="fake_pkg.mod:cmd", load=lambda: _fake_command
    )


def test_plugin_cli_command_cannot_shadow_builtin(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        importlib.metadata, "entry_points", lambda group: [_entry_point("run")]
    )
    builtin_run = cli.commands["run"]
    _add_plugin_cli_commands()
    assert cli.commands["run"] is builtin_run


def test_plugin_cli_command_registers_new_name(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        importlib.metadata,
        "entry_points",
        lambda group: [_entry_point("fakeplugincmd")],
    )
    _add_plugin_cli_commands()
    try:
        assert cli.commands["fakeplugincmd"] is _fake_command
    finally:
        cli.commands.pop("fakeplugincmd", None)
