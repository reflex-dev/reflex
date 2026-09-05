"""Tests for the reflex CLI command tree."""

from __future__ import annotations

import json
import os
import subprocess
import sys

import click.testing
import pytest

from reflex import reflex

_CLI_STARTUP_DENIED_MODULES = frozenset({
    "PIL",
    "alembic",
    "fastapi",
    "granian",
    "httpx",
    "numpy",
    "pandas",
    "plotly",
    "redis",
    "reflex.app",
    "reflex.compiler",
    "reflex.custom_components.custom_components",
    "reflex.model",
    "reflex.state",
    "reflex.utils.frontend_skeleton",
    "reflex.utils.prerequisites",
    "reflex_cli.v2.deploy",
    "reflex_cli.v2.deployments",
    "sqlalchemy",
    "sqlmodel",
    "starlette",
    "uvicorn",
})
_COMPONENT_HELP_DENIED_MODULES = _CLI_STARTUP_DENIED_MODULES - {
    "reflex.custom_components.custom_components"
}


def _run_cli_probe(probe: str) -> dict[str, object]:
    """Run a CLI import probe in a fresh interpreter.

    Args:
        probe: The Python source to execute.

    Returns:
        The JSON object written by the probe.
    """
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
        env={
            **os.environ,
            "REFLEX_CHECK_LATEST_VERSION": "false",
            "REFLEX_TELEMETRY_ENABLED": "false",
        },
    )
    return json.loads(completed.stdout)


@pytest.mark.parametrize(
    ("argv", "denied_modules"),
    [
        (["--help"], _CLI_STARTUP_DENIED_MODULES),
        (["--version"], _CLI_STARTUP_DENIED_MODULES),
        (["run", "--help"], _CLI_STARTUP_DENIED_MODULES),
        (["component", "--help"], _COMPONENT_HELP_DENIED_MODULES),
        (
            ["deploy", "--help"],
            _CLI_STARTUP_DENIED_MODULES - {"reflex_cli.v2.deploy"},
        ),
        (
            ["cloud", "--help"],
            _CLI_STARTUP_DENIED_MODULES - {"reflex_cli.v2.deployments"},
        ),
    ],
    ids=[
        "help",
        "version",
        "run-help",
        "component-help",
        "deploy-help",
        "cloud-help",
    ],
)
def test_cli_startup_does_not_import_runtime_modules(
    argv: list[str], denied_modules: frozenset[str]
):
    """Keep informational CLI paths independent of app and optional runtimes.

    Args:
        argv: The informational command-line arguments to invoke.
        denied_modules: Modules that the command must not import.
    """
    probe = f"""
import json
import sys

from click.testing import CliRunner
from reflex.reflex import cli

result = CliRunner().invoke(cli, {argv!r})
denied = {denied_modules!r}
loaded = sorted(
    module
    for module in denied
    if module in sys.modules
    or any(name.startswith(module + ".") for name in sys.modules)
)
print(json.dumps({{"exit_code": result.exit_code, "loaded": loaded}}))
"""
    outcome = _run_cli_probe(probe)

    assert outcome["exit_code"] == 0
    assert outcome["loaded"] == []


def test_cloud_commands_registered():
    """The hosting CLI commands import, resolve, and dispatch only on demand."""
    probe = """
import json
import sys

import click
from click.testing import CliRunner
from reflex import reflex

deploy_command = reflex.cli.commands["deploy"]
cloud_command = reflex.cli.commands["cloud"]
imported_before = {
    "deploy": "reflex_cli.v2.deploy" in sys.modules,
    "cloud": "reflex_cli.v2.deployments" in sys.modules,
}
unresolved_before = {
    "deploy": deploy_command._resolved_command is None,
    "cloud": cloud_command._resolved_command is None,
}

runner = CliRunner()
deploy_result = runner.invoke(reflex.cli, ["deploy", "--help"])
cloud_result = runner.invoke(reflex.cli, ["cloud", "--help"])

from reflex_cli.v2.deploy import deploy

print(json.dumps({
    "cloud_is_click": isinstance(cloud_command._resolved_command, click.Command),
    "cloud_help_matches": cloud_command.get_short_help_str()
    == cloud_command._resolved_command.get_short_help_str(),
    "cloud_result": cloud_result.exit_code,
    "deploy_help_matches": deploy_command.help == deploy.help,
    "deploy_is_real": deploy_command._resolved_command is deploy,
    "deploy_result": deploy_result.exit_code,
    "imported_before": imported_before,
    "lazy_commands": [
        isinstance(deploy_command, reflex._LazyCommand),
        isinstance(cloud_command, reflex._LazyCommand),
    ],
    "unresolved_before": unresolved_before,
}))
"""
    outcome = _run_cli_probe(probe)

    assert outcome == {
        "cloud_help_matches": True,
        "cloud_is_click": True,
        "cloud_result": 0,
        "deploy_help_matches": True,
        "deploy_is_real": True,
        "deploy_result": 0,
        "imported_before": {"cloud": False, "deploy": False},
        "lazy_commands": [True, True],
        "unresolved_before": {"cloud": True, "deploy": True},
    }


def test_component_command_registered_lazily():
    """The component command preserves its help while loading on demand."""
    command = reflex.cli.commands["component"]

    assert isinstance(command, reflex._LazyCommand)
    result = click.testing.CliRunner().invoke(reflex.cli, ["component", "--help"])

    assert result.exit_code == 0
    resolved_command = command._resolved_command
    assert resolved_command is not None
    assert command.help == resolved_command.help
    assert "CLI for creating custom components." in result.output


def test_lazy_command_delegates_click_introspection():
    """Click integrations inspecting a registered command see its real metadata."""
    command = reflex._LazyCommand(
        "component",
        "reflex.custom_components.custom_components:custom_components_cli",
        help="CLI for creating custom components.",
    )
    context = click.Context(command, info_name="component")

    help_text = command.get_help(context)
    params = command.get_params(context)

    assert "Commands:" in help_text
    assert "build" in help_text
    assert command._resolved_command is not None
    assert params == command._resolved_command.get_params(context)


def test_lazy_command_delegates_direct_invoke(monkeypatch: pytest.MonkeyPatch):
    """Calling Click's public invoke method executes the resolved callback."""
    called = False

    @click.command()
    def implementation():
        nonlocal called
        called = True

    monkeypatch.setattr(
        reflex,
        "import_module",
        lambda name: type("Commands", (), {"implementation": implementation}),
    )
    command = reflex._LazyCommand(
        "implementation",
        "commands:implementation",
        help="Test command.",
    )

    command.invoke(click.Context(command))

    assert called
    assert command._resolved_command is implementation


def test_lazy_command_delegates_direct_metadata(monkeypatch: pytest.MonkeyPatch):
    """Direct reads of Click's command metadata resolve to the implementation."""

    @click.group()
    @click.option("--value")
    def implementation(value: str | None):
        pass

    monkeypatch.setattr(
        reflex,
        "import_module",
        lambda name: type("Commands", (), {"implementation": implementation}),
    )
    command = reflex._LazyCommand(
        "implementation",
        "commands:implementation",
        help="Test command.",
    )

    assert command.no_args_is_help is implementation.no_args_is_help
    assert command.params == implementation.params
    assert command.callback is implementation.callback
    assert command._resolved_command is implementation


def test_lazy_hosting_command_reports_missing_package(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """An unavailable lazy hosting command keeps the install guidance."""

    def missing_import(name: str):
        raise ImportError(name)

    monkeypatch.setattr(reflex, "import_module", missing_import)
    command = reflex._LazyCommand(
        "deploy",
        "reflex_cli.v2.deploy:deploy",
        help="Deploy the app to the Reflex hosting service.",
        optional=True,
    )

    result = click.testing.CliRunner().invoke(
        command, ["--app-name", "demo", "--no-interactive"]
    )

    assert result.exit_code == 1
    assert "pip install reflex-hosting-cli" in caplog.text
    assert "No such option" not in result.output


def test_lazy_hosting_command_keeps_missing_package_help(
    monkeypatch: pytest.MonkeyPatch,
):
    """An unavailable hosting package retains its top-level help description."""
    monkeypatch.setattr(reflex, "find_spec", lambda name: None, raising=False)

    command = reflex._LazyCommand(
        "deploy",
        "reflex_cli.v2.deploy:deploy",
        help="Deploy the app to the Reflex hosting service.",
        optional=True,
    )

    assert command.help == "Requires the reflex-hosting-cli package."


def test_lazy_hosting_command_reports_incompatible_package(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """An outdated hosting module missing the command keeps the install guidance."""
    monkeypatch.setattr(reflex, "import_module", lambda name: object())
    command = reflex._LazyCommand(
        "deploy",
        "reflex_cli.v2.deploy:deploy",
        help="Deploy the app to the Reflex hosting service.",
        optional=True,
    )

    result = click.testing.CliRunner().invoke(command, ["--app-name", "demo"])

    assert result.exit_code == 1
    assert "pip install reflex-hosting-cli" in caplog.text
    assert not isinstance(result.exception, AttributeError)


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


def test_init_records_version_check_after_frontend_setup(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    """A new project's version-check timestamp survives web initialization."""
    events: list[str] = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("reflex.utils.exec.output_system_info", lambda: None)
    monkeypatch.setattr(
        "reflex.utils.prerequisites.validate_app_name", lambda name: name
    )
    monkeypatch.setattr(
        "reflex.utils.prerequisites.initialize_reflex_user_directory", lambda: None
    )
    monkeypatch.setattr(
        "reflex.utils.prerequisites.ensure_reflex_installation_id", lambda: None
    )
    monkeypatch.setattr(
        "reflex.utils.prerequisites.initialize_frontend_dependencies",
        lambda: events.append("frontend"),
    )
    monkeypatch.setattr(
        "reflex.utils.prerequisites.check_latest_package_version",
        lambda package: events.append("version"),
    )
    monkeypatch.setattr(
        "reflex.utils.templates.initialize_app", lambda app_name, template: "blank"
    )
    monkeypatch.setattr(
        "reflex.utils.frontend_skeleton.initialize_gitignore", lambda: None
    )
    monkeypatch.setattr(
        "reflex.utils.frontend_skeleton.initialize_requirements_txt", lambda: False
    )

    reflex._init("demo")

    assert events == ["frontend", "version"]
