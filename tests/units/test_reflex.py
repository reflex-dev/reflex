"""Tests for the reflex CLI command tree."""

from __future__ import annotations

import click
import click.testing
import pytest

from reflex import reflex


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
