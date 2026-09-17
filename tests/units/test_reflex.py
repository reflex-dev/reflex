"""Tests for the reflex CLI command tree."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import click
import click.testing
import pytest
from click.testing import CliRunner
from reflex_base.registry import RegistrationContext

from reflex import reflex
from reflex.minify import clear_config_cache, get_state_full_path
from reflex.state import State
from tests.units.minify_helpers import install_config, set_minify_modes

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


@pytest.fixture
def cli_runner(monkeypatch: pytest.MonkeyPatch) -> CliRunner:
    """Click runner with ``prerequisites.get_compiled_app`` stubbed out.

    Args:
        monkeypatch: The pytest monkeypatch fixture.

    Returns:
        A ``CliRunner`` ready to invoke ``reflex.reflex.cli`` commands.
    """
    from reflex.utils import prerequisites

    monkeypatch.setattr(prerequisites, "get_compiled_app", lambda *a, **kw: mock.Mock())
    return CliRunner()


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


def test_backend_launcher_does_not_import_compiler_or_state() -> None:
    """The backend supervisor must not load the worker's compiler and state."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
from reflex import reflex
from reflex.istate.manager import reset_disk_state_manager
from reflex.utils import build, exec, telemetry

unexpected = {"reflex.state", "reflex.compiler.utils", "sqlalchemy"} & sys.modules.keys()
assert not unexpected, unexpected
""",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


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


def test_lookup_resolves_minified_path(temp_minify_json, cli_runner):
    """Test that lookup resolves a minified path to full state info."""
    from reflex.reflex import cli

    class AppState(State):
        pass

    class ChildState(AppState):
        pass

    install_config(
        states={
            get_state_full_path(AppState): "b",
            get_state_full_path(ChildState): "c",
        },
        include_state_root=True,
    )

    result = cli_runner.invoke(cli, ["minify", "lookup", "b.c"])

    assert result.exit_code == 0, result.output
    assert "AppState" in result.output
    assert "ChildState" in result.output


def test_lookup_accepts_full_wire_path(temp_minify_json, cli_runner):
    """A path copied verbatim from the frontend keeps the root state prefix."""
    from reflex.reflex import cli

    class WirePathState(State):
        pass

    install_config(
        states={get_state_full_path(WirePathState): "b"},
        include_state_root=True,
    )

    result = cli_runner.invoke(
        cli, ["minify", "lookup", "--json", f"{State.get_name()}.b"]
    )

    assert result.exit_code == 0, result.output
    output_data = json.loads(result.output)
    assert [info["class"] for info in output_data] == ["WirePathState"]


@pytest.mark.parametrize("states_mode", [False, True])
def test_lookup_root_prefix_is_env_independent(
    temp_minify_json, cli_runner, monkeypatch, states_mode
):
    """Both spellings of the root prefix resolve, whatever the env var says.

    Args:
        temp_minify_json: The temporary config fixture.
        cli_runner: The click CLI runner.
        monkeypatch: The pytest monkeypatch fixture.
        states_mode: Whether ``REFLEX_MINIFY_STATES`` is on.
    """
    from reflex.reflex import cli

    class RootIdState(State):
        pass

    # "a" is the root's config id; the only real segment is RootIdState's "b".
    install_config(
        states={get_state_full_path(RootIdState): "b"},
        include_state_root=True,
    )
    set_minify_modes(monkeypatch, states=states_mode)
    clear_config_cache()

    for prefix in ("a", RegistrationContext.default_state_name(State)):
        result = cli_runner.invoke(cli, ["minify", "lookup", "--json", f"{prefix}.b"])
        assert result.exit_code == 0, f"{prefix}: {result.output}"
        assert [info["class"] for info in json.loads(result.output)] == [
            RootIdState.__name__
        ], f"{prefix}: {result.output}"


def test_lookup_fails_without_minify_json(temp_minify_json, cli_runner):
    """Test that lookup fails gracefully when minify.json is missing."""
    from reflex.reflex import cli

    clear_config_cache()
    result = cli_runner.invoke(cli, ["minify", "lookup", "a.b"])

    assert result.exit_code == 1
    assert "minify.json does not exist" in result.output


def test_lookup_fails_for_malformed_config(
    temp_minify_json: Path, cli_runner: CliRunner
) -> None:
    """Test that a malformed minify.json exits cleanly, not with a traceback."""
    from reflex.reflex import cli

    (temp_minify_json / "minify.json").write_text("{not json", encoding="utf-8")
    clear_config_cache()

    result = cli_runner.invoke(cli, ["minify", "lookup", "a.b"])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "Invalid JSON" in result.output


def test_lookup_fails_for_invalid_path(temp_minify_json, cli_runner):
    """Test that lookup fails for non-existent minified path."""
    from reflex.reflex import cli

    class InvalidPathState(State):
        pass

    install_config(
        states={get_state_full_path(InvalidPathState): "b"},
        include_state_root=True,
    )
    result = cli_runner.invoke(cli, ["minify", "lookup", "b.xyz"])

    assert result.exit_code == 1
    assert "No state or event handler found" in result.output


def test_lookup_resolves_event_handler(temp_minify_json, cli_runner):
    """The final segment of a copied event name is a handler id, not a state id."""
    from reflex.reflex import cli

    class HandlerLookupState(State):
        def increment(self):
            pass

    state_path = get_state_full_path(HandlerLookupState)
    install_config(
        states={state_path: "b"},
        events={state_path: {"increment": "cX"}},
        include_state_root=True,
    )

    result = cli_runner.invoke(
        cli, ["minify", "lookup", "--json", f"{State.get_name()}.b.cX"]
    )

    assert result.exit_code == 0, result.output
    output_data = json.loads(result.output)
    assert [entry["kind"] for entry in output_data] == ["state", "event"]
    assert {entry["module"] for entry in output_data} == {__name__}
    assert output_data[1]["class"] == "HandlerLookupState"
    assert output_data[1]["handler"] == "increment"
    assert output_data[1]["event_id"] == "cX"
    assert output_data[1]["full_path"] == f"{state_path}.increment"


def test_lookup_event_handler_text_output(temp_minify_json, cli_runner):
    """Text output names the handler after its owning state class."""
    from reflex.reflex import cli

    class HandlerTextState(State):
        def increment(self):
            pass

    state_path = get_state_full_path(HandlerTextState)
    install_config(
        states={state_path: "b"},
        events={state_path: {"increment": "a"}},
        include_state_root=True,
    )

    result = cli_runner.invoke(cli, ["minify", "lookup", "b.a"])

    assert result.exit_code == 0, result.output
    assert f"{__name__}.HandlerTextState.increment" in result.output


def test_lookup_reports_ambiguous_final_segment(temp_minify_json, cli_runner):
    """A final segment that is both a substate id and a handler id yields both."""
    from reflex.reflex import cli

    class AmbiguousParentState(State):
        def increment(self):
            pass

    class AmbiguousChildState(AmbiguousParentState):
        pass

    parent_path = get_state_full_path(AmbiguousParentState)
    install_config(
        states={
            parent_path: "b",
            get_state_full_path(AmbiguousChildState): "a",
        },
        events={parent_path: {"increment": "a"}},
        include_state_root=True,
    )

    result = cli_runner.invoke(cli, ["minify", "lookup", "--json", "b.a"])

    assert result.exit_code == 0, result.output
    output_data = json.loads(result.output)
    assert [(entry["kind"], entry["class"]) for entry in output_data] == [
        ("state", "AmbiguousParentState"),
        ("state", "AmbiguousChildState"),
        ("event", "AmbiguousParentState"),
    ]

    text_result = cli_runner.invoke(cli, ["minify", "lookup", "b.a"])

    assert text_result.exit_code == 0, text_result.output
    assert "is both a state id and an event handler id" in text_result.output
    assert "AmbiguousParentState.increment" in text_result.output


@pytest.mark.parametrize("minified", [True, False])
def test_lookup_bare_root_segment(temp_minify_json, cli_runner, minified):
    """A lone root segment is the root state, not a prefix with nothing behind it.

    Args:
        temp_minify_json: The temporary config fixture.
        cli_runner: The click CLI runner.
        minified: Whether to look the root state up by its minified id.
    """
    from reflex.reflex import cli

    install_config(include_state_root=True)

    segment = "a" if minified else RegistrationContext.default_state_name(State)
    result = cli_runner.invoke(cli, ["minify", "lookup", "--json", segment])

    assert result.exit_code == 0, result.output
    assert [(entry["kind"], entry["class"]) for entry in json.loads(result.output)] == [
        ("state", "State")
    ]


def test_lookup_bare_root_segment_also_matches_root_handler(
    temp_minify_json, cli_runner
):
    """The root state id and a root handler id collide; both are reported."""
    from reflex.reflex import cli

    install_config(
        events={get_state_full_path(State): {"hydrate": "a"}},
        include_state_root=True,
    )

    result = cli_runner.invoke(cli, ["minify", "lookup", "--json", "a"])

    assert result.exit_code == 0, result.output
    assert [
        (entry["kind"], entry.get("handler")) for entry in json.loads(result.output)
    ] == [("state", None), ("event", "hydrate")]


def test_lookup_accepts_unminified_segments(temp_minify_json, cli_runner):
    """States and events minify independently, so either half may be unminified."""
    from reflex.reflex import cli

    class MixedModeState(State):
        def increment(self):
            pass

    state_path = get_state_full_path(MixedModeState)
    install_config(
        states={state_path: "b"},
        events={state_path: {"increment": "c"}},
        include_state_root=True,
    )
    default_name = RegistrationContext.default_state_name(MixedModeState)

    # Only events minified: the state keeps its default name on the wire.
    result = cli_runner.invoke(
        cli, ["minify", "lookup", "--json", f"{State.get_name()}.{default_name}.c"]
    )
    assert result.exit_code == 0, result.output
    assert [(e["kind"], e["class"]) for e in json.loads(result.output)] == [
        ("state", "MixedModeState"),
        ("event", "MixedModeState"),
    ]

    # Only states minified: the handler keeps its Python name.
    result = cli_runner.invoke(cli, ["minify", "lookup", "--json", "b.increment"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)[1]["handler"] == "increment"


def test_lookup_handler_id_only_matches_final_segment(temp_minify_json, cli_runner):
    """A handler id in the middle of a path is an error, not a state."""
    from reflex.reflex import cli

    class MiddleHandlerState(State):
        def increment(self):
            pass

    state_path = get_state_full_path(MiddleHandlerState)
    install_config(
        states={state_path: "b"},
        events={state_path: {"increment": "c"}},
        include_state_root=True,
    )

    result = cli_runner.invoke(cli, ["minify", "lookup", "b.c.d"])

    assert result.exit_code == 1
    assert "No state found for minified segment 'c'" in result.output


def test_lookup_with_json_output(temp_minify_json, cli_runner):
    """Test that lookup with --json flag outputs valid JSON."""
    from reflex.reflex import cli

    class JsonTestState(State):
        pass

    install_config(
        states={get_state_full_path(JsonTestState): "b"},
        include_state_root=True,
    )

    result = cli_runner.invoke(cli, ["minify", "lookup", "--json", "b"])

    assert result.exit_code == 0, result.output
    output_data = json.loads(result.output)
    assert isinstance(output_data, list)
    assert len(output_data) == 1
    assert output_data[0]["class"] == "JsonTestState"
    assert output_data[0]["state_id"] == "b"


@pytest.mark.parametrize("command", ["list", "lookup"])
def test_stdout_is_reserved_before_the_app_loads(
    command, temp_minify_json, monkeypatch, cli_runner
):
    """Reserving after the app loaded would be too late to help.

    Loading the app dry-runs a compile, which logs warnings and
    deprecations; those go to stdout unless it is claimed first.

    Args:
        command: The ``reflex minify`` subcommand under test.
        temp_minify_json: Temporary ``minify.json`` location.
        monkeypatch: The pytest monkeypatch fixture.
        cli_runner: Click runner with the app loader stubbed.
    """
    from reflex_base.utils import log

    from reflex.reflex import cli
    from reflex.utils import prerequisites

    monkeypatch.setattr(log, "_stdout_reserved", False)

    class JsonOutputState(State):
        pass

    install_config(
        states={get_state_full_path(JsonOutputState): "b"},
        include_state_root=True,
    )
    args = ["minify", command, "--json"]
    if command == "lookup":
        args.append("b")

    reserved_when_loading: list[bool] = []

    def _noisy_load(*a, **kw):
        reserved_when_loading.append(log.is_stdout_reserved())
        # Loading an app runs arbitrary module-level code; reserving only
        # covers Reflex's own logging, not a raw write like this one.
        print("noise from the app import")
        return mock.Mock()

    monkeypatch.setattr(prerequisites, "get_compiled_app", _noisy_load)

    result = cli_runner.invoke(cli, args)

    assert reserved_when_loading == [True]
    assert "noise from the app import" not in result.stdout
    json.loads(result.stdout)


@pytest.mark.parametrize("command", ["list", "lookup"])
def test_json_output_does_not_leak_the_stdout_reservation(
    command, temp_minify_json, cli_runner
):
    """The reservation is scoped to the command, not the process.

    A real CLI process exits, but in-process callers would otherwise leave
    every later log write pointed at stderr.

    Args:
        command: The ``reflex minify`` subcommand under test.
        temp_minify_json: Temporary ``minify.json`` location.
        cli_runner: Click runner with the app loader stubbed.
    """
    from reflex_base.utils import log

    from reflex.reflex import cli

    class ReservationState(State):
        pass

    install_config(
        states={get_state_full_path(ReservationState): "b"},
        include_state_root=True,
    )
    args = ["minify", command, "--json"]
    if command == "lookup":
        args.append("b")

    assert cli_runner.invoke(cli, args).exit_code == 0
    assert log.is_stdout_reserved() is False
