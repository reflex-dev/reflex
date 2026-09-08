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


def test_dev_daemon_does_not_disable_backend_fallback(monkeypatch, mocker):
    """The daemon owns compilation only while its process remains alive."""
    import contextlib

    from reflex_base.environment import environment

    from reflex.utils import build, compile_daemon, processes, telemetry

    monkeypatch.setenv("REFLEX_COMPILE_CACHE", "1")
    monkeypatch.delenv("REFLEX_SKIP_COMPILE", raising=False)
    compiled = mocker.patch.object(reflex, "_compile_app")
    mocker.patch.object(build, "setup_frontend")
    mocker.patch.object(telemetry, "send")
    mocker.patch("atexit.register")
    concurrent = mocker.patch.object(
        processes, "run_concurrently_context", return_value=contextlib.nullcontext()
    )
    reflex._run_dev(reflex.constants.RunningMode.FRONTEND_ONLY, None, None, "localhost")
    compiled.assert_called_once()
    assert not environment.REFLEX_SKIP_COMPILE.get()
    commands = concurrent.call_args.args
    assert any(
        command[0] is compile_daemon.run_compile_daemon and command[2] is True
        for command in commands
    )
