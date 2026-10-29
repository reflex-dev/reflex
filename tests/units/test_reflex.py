"""Tests for the reflex CLI command tree."""

from __future__ import annotations

import contextlib
import json
import os
import select
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

import click
import click.testing
import psutil
import pytest
from pytest_mock import MockerFixture
from reflex_base import constants
from reflex_base.environment import environment

from reflex import reflex
from reflex.testing import DEFAULT_TIMEOUT

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
        (["component", "--help"], _CLI_STARTUP_DENIED_MODULES),
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


def test_compile_app_worker_flushes_telemetry(mocker):
    """Flush the completed compile span before an isolated worker exits."""
    app_task = mocker.Mock(return_value=True)
    flush = mocker.patch("reflex_base.otel.flush")

    assert reflex._compile_app_worker(app_task, (True,), {"trigger": "initial"})

    app_task.assert_called_once_with(True, trigger="initial")
    flush.assert_called_once_with()


def test_compile_app_worker_flushes_telemetry_on_failure(mocker):
    """Flush telemetry even when the worker's compile task raises."""
    app_task = mocker.Mock(side_effect=RuntimeError("compile failed"))
    flush = mocker.patch("reflex_base.otel.flush")

    with pytest.raises(RuntimeError, match="compile failed"):
        reflex._compile_app_worker(app_task, (), {})

    flush.assert_called_once_with()


def test_compile_app_sets_start_method_before_compile_pool(mocker: MockerFixture):
    """The start method is fixed before the compile pool spawns any process."""
    from unittest import mock

    from reflex.utils import exec as exec_utils
    from reflex.utils import prerequisites

    calls: list[str] = []
    mocker.patch.object(exec_utils, "should_use_granian", return_value=True)
    mocker.patch.object(exec_utils, "should_prerender_routes", return_value=False)
    mocker.patch.object(
        exec_utils,
        "set_dev_start_method",
        side_effect=lambda: calls.append("start_method"),
    )
    mocker.patch.object(prerequisites, "compile_or_validate_app")

    class FakeExecutor:
        def __init__(self, *_args, **_kwargs):
            calls.append("pool")

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def submit(self, *_args, **_kwargs):
            future = mock.Mock()
            future.result.return_value = True
            return future

    mocker.patch("concurrent.futures.ProcessPoolExecutor", FakeExecutor)

    reflex._compile_app()

    assert calls == ["start_method", "pool"]


@pytest.mark.parametrize(
    ("running_mode", "launcher"),
    [
        (constants.RunningMode.BACKEND_ONLY, "run_backend_prod"),
        (constants.RunningMode.FRONTEND_ONLY, "run_frontend_prod"),
    ],
)
def test_run_prod_sends_telemetry_synchronously(
    mocker, running_mode: constants.RunningMode, launcher: str
):
    """The run-prod event is delivered on the calling thread, before the server.

    The server forks its workers from this process, so the event must not be
    queued on the telemetry thread pool. Going through ``_process_event`` keeps
    the one-time alias migration, which a backend-only run has no other event
    to ride on.
    """
    from reflex.utils import build, exec, processes, telemetry

    config = mocker.patch.object(reflex, "get_config").return_value
    mocker.patch.object(reflex, "_compile_app")
    mocker.patch.object(reflex, "_skip_compile")
    mocker.patch.object(build, "setup_frontend_prod")
    mocker.patch.object(processes, "atexit_handler")
    mocker.patch("atexit.register")
    mocker.patch.object(exec, "notify_app_running")
    mocker.patch.object(exec, "notify_frontend")
    queued = mocker.patch.object(telemetry, "send")
    calls = mocker.Mock()
    calls.attach_mock(mocker.patch.object(telemetry, "_process_event"), "send")
    calls.attach_mock(mocker.patch.object(exec, launcher), "serve")

    reflex._run_prod(running_mode, 8000, "127.0.0.1")

    queued.assert_not_called()
    calls.send.assert_called_once_with("run-prod", config.telemetry_enabled)
    assert [name for name, _args, _kwargs in calls.mock_calls] == ["send", "serve"]


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


_COMPONENT_TEMPLATE_URL = "https://github.com/reflex-dev/component-template"


def test_component_command_is_hidden():
    """The removed component CLI keeps a shim that stays out of the listing."""
    assert reflex.cli.commands["component"].hidden

    result = click.testing.CliRunner().invoke(reflex.cli, ["--help"])

    assert result.exit_code == 0
    listed = [line.split()[0] for line in result.output.splitlines() if line.strip()]
    assert "component" not in listed


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["init"],
        ["build"],
        ["install", "reflex-example"],
        ["share", "--no-interactive"],
        ["--library-name", "reflex-example"],
    ],
)
def test_component_command_points_to_template(
    caplog: pytest.LogCaptureFixture, args: list[str]
):
    """Every removed component subcommand reports where the workflow moved.

    Args:
        caplog: The pytest log capture fixture.
        args: The arguments a user of the old workflow passes.
    """
    result = click.testing.CliRunner().invoke(reflex.cli.commands["component"], args)

    assert result.exit_code == 1
    assert _COMPONENT_TEMPLATE_URL in caplog.text
    assert "No such option" not in result.output
    assert "No such command" not in result.output


@pytest.mark.parametrize("args", [["--help"], ["init", "--help"]])
def test_component_help_points_to_template(
    monkeypatch: pytest.MonkeyPatch, args: list[str]
):
    """Asking the removed component CLI for help prints the pointer.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        args: The help invocation after ``reflex component``.
    """
    from reflex_base.utils import log

    # Registered so teardown restores the variable the CLI callback sets.
    monkeypatch.setenv(log._MANAGED_ENV_VAR, "true")
    try:
        result = click.testing.CliRunner().invoke(reflex.cli, ["component", *args])
    finally:
        log._reset()

    assert result.exit_code == 0, result.output
    assert _COMPONENT_TEMPLATE_URL in result.output


def test_component_command_dispatches_from_cli():
    """``reflex component init`` reaches the shim instead of a usage error."""
    completed = subprocess.run(
        [sys.executable, "-m", "reflex", "component", "init"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
        env={
            **os.environ,
            "REFLEX_CHECK_LATEST_VERSION": "false",
            "REFLEX_TELEMETRY_ENABLED": "false",
        },
    )

    assert completed.returncode == 1, completed.stderr
    assert _COMPONENT_TEMPLATE_URL in completed.stderr
    assert "No such command" not in completed.stderr


def test_lazy_command_delegates_click_introspection(monkeypatch: pytest.MonkeyPatch):
    """Click integrations inspecting a registered command see its real metadata."""

    @click.group()
    def implementation():
        pass

    @implementation.command()
    def build():
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
    context = click.Context(command, info_name="implementation")

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


@pytest.fixture
def init_in_reflex_dir(tmp_path, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Run `_init` from a directory named `reflex` with the setup steps stubbed.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        The app names passed to `initialize_app`.
    """
    initialized: list[str] = []
    app_dir = tmp_path / "reflex"
    app_dir.mkdir()
    monkeypatch.chdir(app_dir)
    for target in (
        "reflex.utils.exec.output_system_info",
        "reflex.utils.prerequisites.initialize_reflex_user_directory",
        "reflex.utils.prerequisites.ensure_reflex_installation_id",
        "reflex.utils.prerequisites.initialize_frontend_dependencies",
        "reflex.utils.frontend_skeleton.initialize_gitignore",
        "reflex.utils.frontend_skeleton.initialize_agents_md",
    ):
        monkeypatch.setattr(target, lambda: None)
    monkeypatch.setattr(
        "reflex.utils.prerequisites.check_latest_package_version", lambda package: None
    )
    monkeypatch.setattr(
        "reflex.utils.templates.initialize_app",
        lambda app_name, template: initialized.append(app_name),
    )
    monkeypatch.setattr(
        "reflex.utils.frontend_skeleton.initialize_requirements_txt", lambda: False
    )
    return initialized


def test_init_existing_app_in_reflex_dir(
    init_in_reflex_dir: list[str], monkeypatch: pytest.MonkeyPatch
):
    """Reinitializing an existing app validates its app_name, not its directory."""
    constants.Config.FILE.write_text("")
    monkeypatch.setattr(
        reflex, "get_config", lambda: SimpleNamespace(app_name="fooapp")
    )

    result = click.testing.CliRunner().invoke(reflex.init, [])

    assert result.exit_code == 0
    assert init_in_reflex_dir == ["fooapp"]


def test_init_new_app_in_reflex_dir(init_in_reflex_dir: list[str]):
    """A new app still cannot be created in a directory named reflex."""
    result = click.testing.CliRunner().invoke(reflex.init, [])

    assert result.exit_code == 1
    assert init_in_reflex_dir == []


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
def test_frontend_preflight_failure_cleans_process(tmp_path):
    ready = tmp_path / "frontend.pid"
    driver = tmp_path / "driver.py"
    driver.write_text(
        """import subprocess, sys, types
from reflex.utils import build, exec as exec_mod, telemetry

def frontend(*args):
    p = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(60)"])
    exec_mod.frontend_process = p
    with open(PIDS, "w") as handshake:
        handshake.write(str(p.pid))
    sys.stderr.write("x" * 131072)
    raise SystemExit(3)

exec_mod.run_frontend = frontend
exec_mod.run_backend = lambda *args: None
telemetry.send = lambda *args, **kwargs: None
build.setup_frontend = lambda *args, **kwargs: None
import reflex.reflex as rx
rx._compile_app = lambda: None
rx.get_config = lambda: types.SimpleNamespace(
    _set_persistent=lambda **kwargs: None,
    loglevel=types.SimpleNamespace(subprocess_level=lambda: None),
)
from reflex_base import constants
rx._run_dev(constants.RunningMode.FULLSTACK, 3000, 8000, "127.0.0.1")
""".replace("PIDS", repr(str(ready)))
    )
    launcher = subprocess.Popen(
        [sys.executable, str(driver)],
        cwd=tmp_path,
        start_new_session=True,
        stderr=subprocess.PIPE,
    )
    child = None
    try:
        _, stderr = launcher.communicate(timeout=DEFAULT_TIMEOUT)
        assert ready.exists(), (
            "frontend did not start: " + stderr.decode(errors="replace")[-1000:]
        )
        child = int(ready.read_text())
        assert launcher.returncode == 3, stderr.decode(errors="replace")[-1000:]
        with contextlib.suppress(psutil.NoSuchProcess):
            assert psutil.Process(child).status() in (
                psutil.STATUS_ZOMBIE,
                psutil.STATUS_DEAD,
            )
    finally:
        if launcher.poll() is None:
            os.killpg(launcher.pid, signal.SIGKILL)
            launcher.communicate(timeout=DEFAULT_TIMEOUT)
        if child is not None:
            with contextlib.suppress(ProcessLookupError):
                os.kill(child, signal.SIGKILL)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
def test_late_frontend_start_stops_after_backend_returns(tmp_path):
    """A frontend started after backend teardown must exit without hanging."""
    pids = tmp_path / "frontend.pid"
    driver = tmp_path / "driver.py"
    driver.write_text(
        """import subprocess, sys, time, types
from pathlib import Path
from reflex.utils import build, exec as exec_mod, processes, telemetry

original_new_process = processes.new_process
def record_process(*args, **kwargs):
    deadline = time.monotonic() + 5
    while not exec_mod._frontend_shutting_down and time.monotonic() < deadline:
        time.sleep(0.01)
    assert exec_mod._frontend_shutting_down
    p = original_new_process(*args, **kwargs)
    with open(PIDS, "w") as handshake:
        handshake.write(str(p.pid))
    return p
processes.new_process = record_process
exec_mod.get_web_dir = lambda: Path.cwd()
exec_mod.get_package_json_and_hash = lambda *args: ({}, "unchanged")
exec_mod.frontend_env = lambda *args: {}
exec_mod.path_ops.get_node_bin_path = lambda: None

def frontend(*args):
    exec_mod.run_process_and_launch_url(
        [sys.executable, "-c", "import time;time.sleep(60)"], True
    )

def backend(*args):
    return None

exec_mod.run_frontend = frontend
exec_mod.run_backend = backend
telemetry.send = lambda *args, **kwargs: None
build.setup_frontend = lambda *args, **kwargs: None
import reflex.reflex as rx
rx._compile_app = lambda: None
rx.get_config = lambda: types.SimpleNamespace(
    _set_persistent=lambda **kwargs: None,
    loglevel=types.SimpleNamespace(subprocess_level=lambda: None),
)
from reflex_base import constants
rx._run_dev(constants.RunningMode.FULLSTACK, 3000, 8000, "127.0.0.1")
""".replace("PIDS", repr(str(pids)))
    )
    launcher = subprocess.Popen(
        [sys.executable, str(driver)],
        cwd=tmp_path,
        start_new_session=True,
        stderr=subprocess.PIPE,
    )
    child = None
    try:
        try:
            launcher.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pytest.fail("late frontend trapped the run after backend returned")
        assert launcher.returncode == 0
        assert pids.exists(), "late frontend never launched"
        child = int(pids.read_text().strip())
        with contextlib.suppress(psutil.NoSuchProcess):
            assert psutil.Process(child).status() in (
                psutil.STATUS_ZOMBIE,
                psutil.STATUS_DEAD,
            )
    finally:
        if launcher.poll() is None:
            os.killpg(launcher.pid, signal.SIGKILL)
            launcher.wait(timeout=DEFAULT_TIMEOUT)
        if child is not None:
            with contextlib.suppress(ProcessLookupError):
                os.kill(child, signal.SIGKILL)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
def test_fullstack_backend_exit_stops_frontend(tmp_path):
    """Frontend must not trap the run after a normal backend return."""
    pids = tmp_path / "frontend.pid"
    driver = tmp_path / "driver.py"
    driver.write_text(
        """import subprocess, sys, time, types
from pathlib import Path
from reflex.utils import build, exec as exec_mod, processes, telemetry

exec_mod.get_web_dir = lambda: Path.cwd()
exec_mod.get_package_json_and_hash = lambda *args: ({}, "unchanged")
exec_mod.frontend_env = lambda *args: {}
exec_mod.path_ops.get_node_bin_path = lambda: None
original_new_process = processes.new_process
def record_process(*args, **kwargs):
    p = original_new_process(*args, **kwargs)
    with open(PIDS, "w") as handshake:
        handshake.write(str(p.pid))
    return p
processes.new_process = record_process
exec_mod.run_frontend = lambda *args: exec_mod.run_process_and_launch_url(
    [sys.executable, "-c", "import time;time.sleep(60)"], True
)
def backend(*args):
    from pathlib import Path
    deadline = time.monotonic() + 5
    while not Path(PIDS).exists() and time.monotonic() < deadline:
        time.sleep(0.01)
exec_mod.run_backend = backend
telemetry.send = lambda *args, **kwargs: None
build.setup_frontend = lambda *args, **kwargs: None
import reflex.reflex as rx
rx._compile_app = lambda: None
rx.get_config = lambda: types.SimpleNamespace(
    _set_persistent=lambda **kwargs: None,
    loglevel=types.SimpleNamespace(subprocess_level=lambda: None),
)
from reflex_base import constants
rx._run_dev(constants.RunningMode.FULLSTACK, 3000, 8000, "127.0.0.1")
""".replace("PIDS", repr(str(pids)))
    )
    launcher = subprocess.Popen(
        [sys.executable, str(driver)],
        cwd=tmp_path,
        start_new_session=True,
        stderr=subprocess.PIPE,
    )
    child = None
    try:
        # The launcher may finish before the parent gets scheduled to observe it.
        _, stderr = launcher.communicate(timeout=DEFAULT_TIMEOUT)
        assert pids.exists(), (
            "frontend did not start: " + stderr.decode(errors="replace")[-1000:]
        )
        child = int(pids.read_text().strip())
        assert launcher.returncode == 0, stderr.decode(errors="replace")[-1000:]
        with contextlib.suppress(psutil.NoSuchProcess):
            assert psutil.Process(child).status() in (
                psutil.STATUS_ZOMBIE,
                psutil.STATUS_DEAD,
            )
    finally:
        if launcher.poll() is None:
            os.killpg(launcher.pid, signal.SIGKILL)
            launcher.communicate(timeout=DEFAULT_TIMEOUT)
        if child is not None:
            with contextlib.suppress(ProcessLookupError):
                os.kill(child, signal.SIGKILL)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups")
@pytest.mark.parametrize("mode", ["frontend", "fullstack"])
def test_sigkill_run_group_stops_frontend(tmp_path, mode):
    """A hard kill of the CLI job group must not leave frontend workers alive."""
    pids = tmp_path / "children"
    driver = tmp_path / "driver.py"
    driver.write_text(
        """import subprocess, sys, time, types
from pathlib import Path
from reflex.utils import build, exec as exec_mod, processes, telemetry

code = "import subprocess,sys,time\\n" + \
    "p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])\\n" + \
    "print(p.pid,flush=True);time.sleep(60)\\n"
exec_mod.get_web_dir=lambda:Path.cwd()
exec_mod.get_package_json_and_hash=lambda *args:({}, "unchanged")
exec_mod.frontend_env=lambda *args:{}
exec_mod.path_ops.get_node_bin_path=lambda:None
original_new_process=processes.new_process
def record_process(*args,**kwargs):
    p=original_new_process(*args,**kwargs)
    with open(PIDS,"w") as handshake:
        handshake.write(str(p.pid))
    return p
processes.new_process=record_process
exec_mod.run_frontend=lambda *args:exec_mod.run_process_and_launch_url(
    [sys.executable,"-c",code],True
)
exec_mod.run_backend=lambda *args: time.sleep(60)
telemetry.send=lambda *a,**k:None
build.setup_frontend=lambda *a,**k:None
import reflex.reflex as rx
rx._compile_app=lambda:None
rx.get_config=lambda:types.SimpleNamespace(_set_persistent=lambda **k:None,
    loglevel=types.SimpleNamespace(subprocess_level=lambda:None))
from reflex_base import constants
rx._run_dev(MODE,3000,PORT,"127.0.0.1")
"""
        .replace("PIDS", repr(str(pids)))
        .replace(
            "MODE",
            "constants.RunningMode.FRONTEND_ONLY"
            if mode == "frontend"
            else "constants.RunningMode.FULLSTACK",
        )
        .replace("PORT", "None" if mode == "frontend" else "8000")
    )
    launcher = subprocess.Popen(
        [sys.executable, str(driver)],
        cwd=tmp_path,
        start_new_session=True,
        stderr=subprocess.PIPE,
        text=True,
    )
    child = grandchild = None
    try:
        deadline = time.monotonic() + DEFAULT_TIMEOUT
        while time.monotonic() < deadline:
            if launcher.poll() is not None:
                pytest.fail(f"launcher exited early: {launcher.returncode}")
            if pids.exists():
                parts = pids.read_text().split()
                if len(parts) == 1:
                    child = int(parts[0])
                    children = psutil.Process(child).children()
                    if children:
                        grandchild = children[0].pid
                        break
            time.sleep(0.01)
        assert child is not None
        assert grandchild is not None
        assert os.getpgid(child) == launcher.pid
        os.killpg(launcher.pid, signal.SIGKILL)
        launcher.wait(timeout=DEFAULT_TIMEOUT)
        for pid in (child, grandchild):
            deadline = time.monotonic() + DEFAULT_TIMEOUT
            while time.monotonic() < deadline:
                try:
                    if psutil.Process(pid).status() in (
                        psutil.STATUS_ZOMBIE,
                        psutil.STATUS_DEAD,
                    ):
                        break
                except psutil.NoSuchProcess:
                    break
                time.sleep(0.05)
            else:
                pytest.fail(f"frontend descendant {pid} survived SIGKILL")
    finally:
        if launcher.poll() is None:
            os.killpg(launcher.pid, signal.SIGKILL)
            launcher.wait(timeout=DEFAULT_TIMEOUT)
        if child is not None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(child, signal.SIGKILL)
        for pid in (child, grandchild):
            if pid is not None:
                with contextlib.suppress(ProcessLookupError):
                    os.kill(pid, signal.SIGKILL)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
@pytest.mark.parametrize("mode", ["frontend", "fullstack"])
@pytest.mark.parametrize("sig", ["SIGTERM", "SIGINT"])
@pytest.mark.parametrize("forwards", [True, False], ids=["forwarding", "orphaning"])
def test_no_tty_run_stops_frontend(tmp_path, mode, sig, forwards):
    """Headless runs stop the frontend on SIGTERM or SIGINT.

    The frontend stand-in either passes SIGTERM on to its own child, as bun
    does, or exits without it, as ``npm run`` does; the child must stop either way.
    """
    pids = tmp_path / "children"
    driver = tmp_path / "driver.py"
    driver.write_text(
        """import signal, subprocess, sys, time, types
from reflex.utils import build, exec as exec_mod, telemetry

def frontend(*args):
    code = "import signal,subprocess,sys,time\\n" + \
        "p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])\\n" + \
        ("signal.signal(signal.SIGTERM, lambda *a: (p.terminate(), sys.exit(0)))\\n" if FORWARDS else "") + \
        "print(p.pid,flush=True);time.sleep(60)\\n"
    p = subprocess.Popen([sys.executable,"-c",code],stdout=subprocess.PIPE,text=True)
    grandchild = int(p.stdout.readline())
    exec_mod.frontend_process = p
    with open(PIDS,"w") as handshake:
        handshake.write(f"{p.pid} {grandchild}")
    p.wait()

def backend(*args):
    def stop(sig,frame): raise SystemExit(0)
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    while True: time.sleep(1)

exec_mod.run_frontend=frontend
exec_mod.run_backend=backend
telemetry.send=lambda *a,**k:None
build.setup_frontend=lambda *a,**k:None
import reflex.reflex as rx
rx._compile_app=lambda:None
rx.get_config=lambda:types.SimpleNamespace(_set_persistent=lambda **k:None,
    loglevel=types.SimpleNamespace(subprocess_level=lambda:None))
from reflex_base import constants
rx._run_dev(MODE,3000,PORT,"127.0.0.1")
"""
        .replace("PIDS", repr(str(pids)))
        .replace("FORWARDS", repr(forwards))
        .replace(
            "MODE",
            "constants.RunningMode.FRONTEND_ONLY"
            if mode == "frontend"
            else "constants.RunningMode.FULLSTACK",
        )
        .replace("PORT", "None" if mode == "frontend" else "8000")
    )
    launcher = subprocess.Popen(
        [sys.executable, str(driver)],
        cwd=tmp_path,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    child = grandchild = None
    try:
        deadline = time.monotonic() + DEFAULT_TIMEOUT
        while time.monotonic() < deadline:
            if launcher.poll() is not None:
                pytest.fail(f"launcher exited early: {launcher.returncode}")
            if pids.exists():
                parts = pids.read_text().split()
                if len(parts) == 2:
                    child, grandchild = map(int, parts)
                    break
            time.sleep(0.01)
        assert child is not None, "frontend did not start"
        assert grandchild is not None, "frontend grandchild did not start"
        started = time.monotonic()
        os.kill(launcher.pid, getattr(signal, sig))
        try:
            returncode = launcher.wait(timeout=DEFAULT_TIMEOUT)
        except subprocess.TimeoutExpired:
            pytest.fail("no-TTY launcher hung after signal")
        # Stopping the tree takes one SIGTERM round, well below the kill timeout.
        assert time.monotonic() - started < 4
        if sig == "SIGINT":
            assert returncode in (0, -signal.SIGINT)
        else:
            assert returncode == 0
        for pid in (child, grandchild):
            deadline = time.monotonic() + DEFAULT_TIMEOUT
            while time.monotonic() < deadline:
                try:
                    if psutil.Process(pid).status() in (
                        psutil.STATUS_ZOMBIE,
                        psutil.STATUS_DEAD,
                    ):
                        break
                except psutil.NoSuchProcess:
                    break
                time.sleep(0.05)
            else:
                pytest.fail(f"frontend descendant {pid} survived signal")
    finally:
        if launcher.poll() is None:
            os.killpg(launcher.pid, signal.SIGKILL)
            launcher.wait(timeout=DEFAULT_TIMEOUT)
        if child is not None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(child, signal.SIGKILL)
        for pid in (child, grandchild):
            if pid is not None:
                with contextlib.suppress(ProcessLookupError):
                    os.kill(pid, signal.SIGKILL)


_STUCK_CLEANUP_SCRIPT = """
import os, signal, subprocess, sys, threading, time

from reflex import reflex

with reflex._shutdown_signals() as begin_cleanup:
    try:
        served = threading.Event()
        if os.environ.get("SERVER_HANDLERS"):
            # Like granian: its own handlers while serving, never restored.
            for sig in (signal.SIGINT, signal.SIGTERM):
                signal.signal(sig, lambda *_: served.set())
        print("ready", flush=True)
        while not served.is_set():
            time.sleep(0.05)
    finally:
        begin_cleanup()
        # A cleanup that never ends, like a frontend pipe held open forever.
        helper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        print(helper.pid, flush=True)
        while True:
            time.sleep(1)
"""


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
@pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGTERM])
@pytest.mark.parametrize("server_handlers", [False, True], ids=["own", "server"])
def test_shutdown_signals_force_exit_on_a_later_repeat(tmp_path, sig, server_handlers):
    """A repeat right after the first signal is ignored; a later one forces the exit.

    A backend server that installed its own handlers and never restored them,
    as granian does, cannot swallow the later repeat.
    """
    script = tmp_path / "stuck.py"
    script.write_text(_STUCK_CLEANUP_SCRIPT)
    proc = subprocess.Popen(
        [sys.executable, str(script)],
        stdout=subprocess.PIPE,
        bufsize=0,
        env={**os.environ, "SERVER_HANDLERS": "1" if server_handlers else ""},
    )
    helper = None
    try:
        assert _read_line(proc) == "ready\n"
        proc.send_signal(sig)
        helper = int(_read_line(proc))
        # The same Ctrl-C delivered twice under --json: not a request to force.
        proc.send_signal(sig)
        time.sleep(0.3)
        assert proc.poll() is None
        time.sleep(reflex._REPEAT_IGNORE_SECONDS)
        proc.send_signal(sig)
        assert proc.wait(timeout=DEFAULT_TIMEOUT) == 128 + sig
        _assert_gone(helper, "the forced exit left the cleanup's child running")
    finally:
        proc.kill()
        proc.wait()
        if helper is not None:
            with contextlib.suppress(ProcessLookupError):
                os.kill(helper, signal.SIGKILL)


def _read_line(proc: subprocess.Popen) -> str:
    """Read one line from a child's unbuffered stdout, failing instead of hanging.

    Args:
        proc: The child, started with ``stdout=PIPE`` and ``bufsize=0`` so no
            later line is read ahead into a buffer ``select`` cannot see.

    Returns:
        The decoded line, newline included.
    """
    assert proc.stdout is not None
    if not select.select([proc.stdout], [], [], DEFAULT_TIMEOUT)[0]:
        pytest.fail("the child printed nothing in time")
    return proc.stdout.readline().decode()


def _assert_gone(pid: int, message: str) -> None:
    """Wait for a process to exit; an exited process nobody reaped counts.

    Args:
        pid: The process ID.
        message: The failure message when it keeps running.
    """
    deadline = time.monotonic() + DEFAULT_TIMEOUT
    while time.monotonic() < deadline:
        try:
            if psutil.Process(pid).status() == psutil.STATUS_ZOMBIE:
                return
        except psutil.NoSuchProcess:
            return
        time.sleep(0.05)
    pytest.fail(message)


@pytest.mark.skipif(sys.platform != "linux", reason="fills a pipe by whole pages")
def test_shutdown_signals_force_exit_with_a_full_stderr(tmp_path):
    """A stderr nobody reads cannot hold up the forced exit."""
    script = tmp_path / "stuck.py"
    script.write_text(_STUCK_CLEANUP_SCRIPT)
    read_end, write_end = os.pipe()
    proc = subprocess.Popen(
        [sys.executable, str(script)],
        stdout=subprocess.PIPE,
        stderr=write_end,
        bufsize=0,
    )
    helper = None
    try:
        assert _read_line(proc) == "ready\n"
        proc.send_signal(signal.SIGTERM)
        helper = int(_read_line(proc))
        # Fill the pipe; its write end stays open here, so nothing drains it.
        while select.select([], [write_end], [], 0)[1]:
            os.write(write_end, b"\0" * select.PIPE_BUF)
        time.sleep(reflex._REPEAT_IGNORE_SECONDS + 0.1)
        proc.send_signal(signal.SIGTERM)
        assert proc.wait(timeout=DEFAULT_TIMEOUT) == 128 + signal.SIGTERM
        _assert_gone(helper, "the forced exit left the cleanup's child running")
    finally:
        proc.kill()
        proc.wait()
        os.close(read_end)
        os.close(write_end)
        if helper is not None:
            with contextlib.suppress(ProcessLookupError):
                os.kill(helper, signal.SIGKILL)


# A dev server that ignores SIGTERM behind a wrapper that exits on it, like a
# package manager in front of the server.
_SERVER_BEHIND_WRAPPER_SCRIPT = """
import subprocess, sys, time

server = subprocess.Popen(
    [
        sys.executable,
        "-c",
        "import signal, time\\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\\n"
        "print('ready', flush=True)\\n"
        "time.sleep(60)",
    ],
    stdout=subprocess.PIPE,
    text=True,
)
# Only report the server once it ignores SIGTERM.
server.stdout.readline()
print(server.pid, flush=True)
time.sleep(60)
"""

_ORPHANING_CLEANUP_SCRIPT = """
import subprocess, sys, time

from reflex import reflex
from reflex_base.utils.process_tree import stop_process_tree

wrapper = subprocess.Popen(
    [sys.executable, sys.argv[1]], stdout=subprocess.PIPE, text=True
)
print(wrapper.stdout.readline(), end="", flush=True)
with reflex._shutdown_signals() as begin_cleanup:
    try:
        print("ready", flush=True)
        while True:
            time.sleep(1)
    finally:
        begin_cleanup()
        # The wrapper exits at once; the server holds the stop until the deadline.
        stop_process_tree(wrapper, timeout=60)
"""


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
def test_shutdown_signals_force_exit_kills_an_orphaned_descendant(tmp_path):
    """The forced exit kills a server whose wrapper exited during the cleanup."""
    wrapper_script = tmp_path / "wrapper.py"
    wrapper_script.write_text(_SERVER_BEHIND_WRAPPER_SCRIPT)
    script = tmp_path / "stuck.py"
    script.write_text(_ORPHANING_CLEANUP_SCRIPT)
    proc = subprocess.Popen(
        [sys.executable, str(script), str(wrapper_script)],
        stdout=subprocess.PIPE,
        bufsize=0,
    )
    server = None
    try:
        server = int(_read_line(proc))
        assert _read_line(proc) == "ready\n"
        proc.send_signal(signal.SIGTERM)
        # By now the wrapper is gone and the server is no longer found below the run.
        time.sleep(reflex._REPEAT_IGNORE_SECONDS + 0.2)
        assert proc.poll() is None
        proc.send_signal(signal.SIGTERM)
        assert proc.wait(timeout=DEFAULT_TIMEOUT) == 128 + signal.SIGTERM
        _assert_gone(server, "the forced exit left the orphaned server running")
    finally:
        proc.kill()
        proc.wait()
        if server is not None:
            with contextlib.suppress(ProcessLookupError):
                os.kill(server, signal.SIGKILL)


@pytest.mark.parametrize(
    ("argv", "supervised", "expected"),
    [(["--json"], False, True), (["--json"], True, False), ([], False, False)],
)
def test_run_supervises_output_only_in_json_mode(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
    supervised: bool,
    expected: bool,
):
    """``reflex run --json`` runs itself again below an output supervisor.

    Args:
        mocker: The pytest-mock fixture.
        monkeypatch: The pytest monkeypatch fixture.
        argv: Extra ``reflex run`` arguments.
        supervised: Whether the process already runs under the supervisor.
        expected: Whether the supervisor is expected to start.
    """
    from reflex_base.environment import environment
    from reflex_base.utils import log, supervisor

    # Registered so teardown restores the variables the CLI callbacks set.
    monkeypatch.setenv(log._MANAGED_ENV_VAR, "true")
    monkeypatch.setenv(environment.REFLEX_LOG_JSON.name, "false")
    monkeypatch.setenv(supervisor._SUPERVISED_ENV_VAR, "1234" if supervised else "")
    monkeypatch.setattr(sys, "argv", ["reflex", "run", *argv])
    supervise = mocker.patch.object(supervisor, "supervise_output", return_value=7)
    run = mocker.patch.object(reflex, "_run")
    mocker.patch("reflex.utils.prerequisites.check_running_mode")

    try:
        result = click.testing.CliRunner().invoke(reflex.cli, ["run", *argv])
    finally:
        log._reset()

    if expected:
        assert result.exit_code == 7
        supervise.assert_called_once_with([
            sys.executable,
            "-m",
            "reflex",
            "run",
            *argv,
        ])
        run.assert_not_called()
    else:
        assert result.exit_code == 0, result.output
        supervise.assert_not_called()
        run.assert_called_once()


@pytest.fixture
def run_cli_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unset the variables ``reflex run`` reads or sets, and restore them after.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
    """
    for var in (
        environment.REFLEX_COMPILE_CONTEXT,
        environment.REFLEX_FRONTEND_ONLY,
        environment.REFLEX_BACKEND_ONLY,
        environment.REFLEX_FRONTEND_PORT,
        environment.REFLEX_BACKEND_PORT,
        environment.REFLEX_LOG_JSON,
    ):
        monkeypatch.delenv(var.name, raising=False)


@pytest.mark.usefixtures("run_cli_env")
@pytest.mark.parametrize(
    ("argv", "frontend_port", "backend_port"),
    [
        ([], 3653, 8653),
        (["--frontend-only"], 3653, None),
        (["--backend-only"], None, 8653),
        (["--frontend-only", "--frontend-port", "3001"], 3001, None),
        (["--backend-only", "--backend-port", "8001"], None, 8001),
    ],
)
def test_run_uses_config_ports_only_for_the_running_side(
    mocker: MockerFixture,
    argv: list[str],
    frontend_port: int | None,
    backend_port: int | None,
):
    """A port set in rxconfig.py does not reach ``_run`` for a side that does not run.

    Args:
        mocker: The pytest-mock fixture.
        argv: Extra ``reflex run`` arguments.
        frontend_port: The frontend port expected to reach ``_run``.
        backend_port: The backend port expected to reach ``_run``.
    """
    config = mocker.patch.object(reflex, "get_config").return_value
    config.frontend_port = 3653
    config.backend_port = 8653
    run = mocker.patch.object(reflex, "_run")

    result = click.testing.CliRunner().invoke(reflex.cli, ["run", *argv])

    assert result.exit_code == 0, result.output
    assert run.call_args.kwargs["frontend_port"] == frontend_port
    assert run.call_args.kwargs["backend_port"] == backend_port


@pytest.mark.usefixtures("run_cli_env")
@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (
            ["--frontend-only", "--backend-port", "8001"],
            "Cannot specify --backend-port when not running backend.",
        ),
        (
            ["--backend-only", "--frontend-port", "3001"],
            "Cannot specify --frontend-port when not running frontend.",
        ),
    ],
)
def test_run_rejects_a_port_flag_for_the_side_that_does_not_run(
    mocker: MockerFixture,
    caplog: pytest.LogCaptureFixture,
    argv: list[str],
    message: str,
):
    """An explicit port flag for the side that does not run is still an error.

    Args:
        mocker: The pytest-mock fixture.
        caplog: The pytest log capture fixture.
        argv: Extra ``reflex run`` arguments.
        message: The expected error message.
    """
    config = mocker.patch.object(reflex, "get_config").return_value
    config.frontend_port = 3653
    config.backend_port = 8653

    result = click.testing.CliRunner().invoke(reflex.cli, ["run", *argv])

    assert result.exit_code == 1
    assert message in caplog.text


@pytest.mark.parametrize(
    "args", [["init"], ["migrate"], ["makemigrations"], ["status"]]
)
def test_db_commands_without_db_extra_point_to_install(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, args: list[str]
):
    """Without the db extra, db commands print the install hint instead of a traceback."""
    monkeypatch.setattr(reflex, "find_spec", lambda name: None)

    result = click.testing.CliRunner().invoke(reflex.db_cli, args)

    assert result.exit_code == 1
    assert "pip install reflex[db]" in caplog.text
    assert not isinstance(result.exception, ImportError)


@pytest.mark.parametrize("missing", reflex._DB_PACKAGES)
def test_db_commands_with_partial_db_install_point_to_install(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, missing: str
):
    """A partial install missing any one db package still gets the install hint."""
    real_find_spec = reflex.find_spec
    monkeypatch.setattr(
        reflex,
        "find_spec",
        lambda name: None if name == missing else real_find_spec(name),
    )

    result = click.testing.CliRunner().invoke(reflex.db_cli, ["init"])

    assert result.exit_code == 1
    assert "pip install reflex[db]" in caplog.text
    assert not isinstance(result.exception, ImportError)


def test_db_commands_run_without_sqlmodel(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """Db commands run with sqlalchemy and alembic installed but not sqlmodel."""
    from reflex.utils import prerequisites

    monkeypatch.setattr(
        reflex, "find_spec", lambda name: None if name == "sqlmodel" else object()
    )
    monkeypatch.setattr(prerequisites, "get_app", lambda: None)
    monkeypatch.setattr(prerequisites, "check_db_initialized", lambda: False)

    result = click.testing.CliRunner().invoke(reflex.db_cli, ["migrate"])

    assert result.exit_code == 0, result.output
    assert "pip install reflex[db]" not in caplog.text


@pytest.fixture
def patched_production_startup(mocker: MockerFixture) -> dict:
    """Patch process startup while retaining the production command sequence.

    Returns:
        Mocked startup operations and the frontend lock context.
    """
    config = mocker.patch("reflex.reflex.get_config", return_value=mocker.Mock())
    mocker.patch("reflex.reflex._skip_compile")
    mocker.patch("atexit.register")
    mocker.patch("reflex.utils.telemetry.send")
    mocker.patch("reflex.utils.exec.notify_app_running")
    mocker.patch("reflex.utils.exec.notify_frontend")
    mount_frontend = mocker.patch(
        "reflex.reflex.environment.REFLEX_MOUNT_FRONTEND_COMPILED_APP"
    ).set
    return {
        "config": config.return_value,
        "mount_frontend": mount_frontend,
        "lock": mocker.patch("reflex.utils.path_ops.file_lock"),
        "compile": mocker.patch("reflex.reflex._compile_app"),
        "setup": mocker.patch("reflex.utils.build.setup_frontend_prod"),
        "backend_prod": mocker.patch("reflex.utils.exec.run_backend_prod"),
        "backend_preview": mocker.patch("reflex.utils.exec.run_backend"),
        "frontend": mocker.patch("reflex.utils.exec.run_frontend_prod"),
    }


@pytest.mark.parametrize("runner_name", ["_run_prod", "_run_preview"])
@pytest.mark.parametrize(
    "running_mode",
    [constants.RunningMode.FULLSTACK, constants.RunningMode.FRONTEND_ONLY],
)
def test_production_startup_locks_compile_and_build_before_serving(
    patched_production_startup, runner_name: str, running_mode: constants.RunningMode
):
    """Only compile and build hold the lock; serving starts after release."""
    context = patched_production_startup["lock"].return_value

    def require_lock(*args, **kwargs):
        """Compilation and setup share the same unreleased lock."""
        context.__enter__.assert_called_once()
        context.__exit__.assert_not_called()

    def require_release(*args, **kwargs):
        """Serving must not retain the frontend lock for the server lifetime."""
        context.__exit__.assert_called_once_with(None, None, None)

    patched_production_startup["compile"].side_effect = require_lock
    patched_production_startup["setup"].side_effect = require_lock
    patched_production_startup["config"]._set_persistent.side_effect = require_lock
    patched_production_startup["mount_frontend"].side_effect = require_lock
    for server in ("backend_prod", "backend_preview", "frontend"):
        patched_production_startup[server].side_effect = require_release

    getattr(reflex, runner_name)(running_mode, 8000, "127.0.0.1")

    patched_production_startup["lock"].assert_called_once()
    patched_production_startup["setup"].assert_called_once()
    patched_production_startup["config"]._set_persistent.assert_called_once_with(
        frontend_port=8000, backend_port=8000
    )
    server = (
        "frontend"
        if running_mode == constants.RunningMode.FRONTEND_ONLY
        else "backend_prod"
        if runner_name == "_run_prod"
        else "backend_preview"
    )
    patched_production_startup[server].assert_called_once()


@pytest.mark.parametrize("runner_name", ["_run_prod", "_run_preview"])
@pytest.mark.parametrize("failing_target", ["compile", "setup"])
def test_production_startup_releases_lock_after_failed_build(
    patched_production_startup, runner_name: str, failing_target: str
):
    """A startup failure releases the lock and does not start a server."""
    error = RuntimeError("build failed")
    patched_production_startup[failing_target].side_effect = error
    with pytest.raises(RuntimeError, match="build failed"):
        getattr(reflex, runner_name)(constants.RunningMode.FULLSTACK, 8000, "127.0.0.1")

    context = patched_production_startup["lock"].return_value
    context.__enter__.assert_called_once()
    context.__exit__.assert_called_once()
    assert context.__exit__.call_args.args[:2] == (RuntimeError, error)
    for server in ("backend_prod", "backend_preview", "frontend"):
        patched_production_startup[server].assert_not_called()


@pytest.mark.parametrize("runner_name", ["_run_prod", "_run_preview"])
def test_backend_only_startup_does_not_lock_frontend(
    patched_production_startup, runner_name: str
):
    """Backend-only startup does not access the frontend working directory."""
    getattr(reflex, runner_name)(constants.RunningMode.BACKEND_ONLY, 8000, "127.0.0.1")

    patched_production_startup["lock"].assert_not_called()
    patched_production_startup["compile"].assert_not_called()
    patched_production_startup["setup"].assert_not_called()
    patched_production_startup["config"]._set_persistent.assert_called_once_with(
        frontend_port=8000, backend_port=8000
    )
    if runner_name == "_run_preview":
        patched_production_startup["mount_frontend"].assert_called_once_with(False)
