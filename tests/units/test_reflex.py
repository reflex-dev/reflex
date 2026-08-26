"""Tests for the reflex CLI module."""

import importlib.metadata
from types import SimpleNamespace

import click
import pytest

from reflex.reflex import _add_plugin_cli_commands, cli


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
