"""Tests for the reflex CLI command tree."""

from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from unittest import mock

import click
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


def test_run_dev_frontend_only_holds_for_frontend_lifetime(monkeypatch, tmp_path):
    """Frontend-only dev run keeps the run context open for the frontend.

    Regression test: with no backend occupying the with-body, the body must
    hold on the frontend task; an empty body unwinds run_concurrently_context
    immediately and tears down the freshly launched frontend dev server.
    """
    import threading
    import time

    from reflex_base import constants

    from reflex.testing import DEFAULT_TIMEOUT
    from reflex.utils import processes

    config_mock = mock.Mock()
    monkeypatch.setattr(reflex, "get_config", lambda: config_mock)
    monkeypatch.setattr(reflex, "_compile_app", lambda: None)
    monkeypatch.setattr("reflex.utils.telemetry.send", lambda *a, **k: None)
    monkeypatch.setattr("reflex.utils.build.setup_frontend", lambda *a, **k: None)
    monkeypatch.setattr("atexit.register", lambda *a, **k: None)

    frontend: dict[str, subprocess.Popen] = {}

    def _fake_run_frontend(root, port, backend_present):
        child = processes.new_process(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            run_managed=True,
        )
        frontend["child"] = child
        child.wait()

    monkeypatch.setattr("reflex.utils.exec.run_frontend", _fake_run_frontend)

    errors: list[BaseException] = []

    def _run():
        try:
            reflex._run_dev(
                constants.RunningMode.FRONTEND_ONLY,
                frontend_port=3000,
                backend_port=None,
                backend_host="0.0.0.0",
            )
        except BaseException as e:
            errors.append(e)

    runner = threading.Thread(target=_run)
    runner.start()
    try:
        deadline = time.monotonic() + DEFAULT_TIMEOUT
        while "child" not in frontend and time.monotonic() < deadline:
            time.sleep(0.01)
        assert "child" in frontend, "frontend child never started"
        child = frontend["child"]
        time.sleep(0.3)
        assert runner.is_alive(), "frontend-only run exited while the frontend lived"
        assert child.poll() is None, "frontend child was terminated at startup"
        child.terminate()
        runner.join(timeout=DEFAULT_TIMEOUT)
        assert not runner.is_alive(), "frontend-only run hung after frontend exit"
        assert errors == []
    finally:
        if "child" in frontend and frontend["child"].poll() is None:
            frontend["child"].kill()
            frontend["child"].wait()
        runner.join(timeout=DEFAULT_TIMEOUT)


_FRONTEND_ONLY_DRIVER = """
import sys
import types

GC_FILE = {gc_file!r}

from reflex.utils import build, exec as exec_mod, processes, telemetry

_CHILD_TREE = (
    "import subprocess, sys, time\\n"
    "g = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\\n"
    f"open({{GC_FILE!r}}, 'w').write(str(g.pid))\\n"
    "time.sleep(60)\\n"
)


def fake_frontend(root, port, backend_present):
    child = processes.new_process(
        [sys.executable, "-c", _CHILD_TREE], run_managed=True, start_new_session=True
    )
    print(f"READY {{child.pid}}", flush=True)
    child.wait()


exec_mod.run_frontend = fake_frontend
telemetry.send = lambda *a, **k: None
build.setup_frontend = lambda *a, **k: None

import reflex.reflex as reflex_module

reflex_module._compile_app = lambda: None
reflex_module.get_config = lambda: types.SimpleNamespace(
    _set_persistent=lambda **k: None
)

from reflex_base import constants

reflex_module._run_dev(
    constants.RunningMode.FRONTEND_ONLY,
    frontend_port=3000,
    backend_port=None,
    backend_host="0.0.0.0",
)
"""


def _pid_gone(pid: int) -> bool:
    """Check whether nothing runnable remains at a pid.

    Args:
        pid: The process ID.

    Returns:
        True when the pid is gone or a zombie awaiting reap by its new parent.
    """
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    if sys.platform == "linux":
        stat = Path(f"/proc/{pid}/stat")
        if stat.exists():
            try:
                return stat.read_text().split()[2] in ("Z", "X")
            except FileNotFoundError:
                return True
    import psutil

    try:
        return psutil.Process(pid).status() in (
            psutil.STATUS_ZOMBIE,
            psutil.STATUS_DEAD,
        )
    except psutil.NoSuchProcess:
        return True


@pytest.mark.skipif(sys.platform == "win32", reason="signal semantics are POSIX")
@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT])
def test_run_dev_frontend_only_signal_tears_down_tree(sig, tmp_path):
    """A no-TTY frontend-only dev run exits cleanly on SIGTERM/SIGINT.

    Real process-level regression test: the launcher must unwind the run
    context (rc 0) instead of dying by the raw signal, and the detached
    frontend tree - a stand-in child and its grandchild for bun/node - must
    be gone afterwards.
    """
    import signal as signal_mod
    import time

    from reflex.testing import DEFAULT_TIMEOUT

    driver = tmp_path / "frontend_only_driver.py"
    gc_file = tmp_path / "grandchild.pid"
    driver.write_text(_FRONTEND_ONLY_DRIVER.format(gc_file=str(gc_file)))

    proc = subprocess.Popen(
        [sys.executable, str(driver)],
        cwd=tmp_path,
        start_new_session=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    child_pid = None
    try:
        assert proc.stdout is not None
        ready = ""
        for line in proc.stdout:
            if line.startswith("READY"):
                ready = line
                break
        assert ready, f"driver never became ready: {proc.stdout.read()}"
        child_pid = int(ready.split()[1])
        deadline = time.monotonic() + DEFAULT_TIMEOUT
        while not gc_file.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert gc_file.exists(), "frontend grandchild never spawned"
        grandchild_pid = int(gc_file.read_text().strip())

        os.kill(proc.pid, sig)
        returncode = proc.wait(timeout=DEFAULT_TIMEOUT)
        assert returncode == 0, (
            f"frontend-only launcher died by signal instead of unwinding (rc {returncode})"
        )
        deadline = time.monotonic() + DEFAULT_TIMEOUT
        while (
            not (_pid_gone(child_pid) and _pid_gone(grandchild_pid))
            and time.monotonic() < deadline
        ):
            time.sleep(0.05)
        assert _pid_gone(child_pid), "frontend child survived launcher shutdown"
        assert _pid_gone(grandchild_pid), (
            "frontend grandchild survived launcher shutdown"
        )
    finally:
        if proc.poll() is None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(proc.pid, signal_mod.SIGKILL)
            proc.wait(timeout=DEFAULT_TIMEOUT)
        for pid in [child_pid] if child_pid else []:
            if not _pid_gone(pid):
                with contextlib.suppress(ProcessLookupError):
                    os.kill(pid, signal_mod.SIGKILL)


def _run_driver(
    driver: Path, timeout: float, *pid_files: Path
) -> subprocess.CompletedProcess:
    """Run a driver subprocess, reaping any recorded child pids afterwards.

    Args:
        driver: The driver script to run.
        timeout: Seconds before subprocess.run kills the driver.
        pid_files: Files the driver writes spawned child pids into.

    Returns:
        The completed process.
    """
    try:
        return subprocess.run(
            [sys.executable, str(driver)],
            cwd=driver.parent,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    finally:
        # subprocess.run kills the driver itself on timeout; the detached
        # children it recorded would survive, so reap them here.
        for pid_file in pid_files:
            if not pid_file.exists():
                continue
            with contextlib.suppress(ValueError):
                pid = int(pid_file.read_text().strip())
                if not _pid_gone(pid):
                    with contextlib.suppress(ProcessLookupError):
                        os.kill(pid, signal.SIGKILL)


_FRONTEND_ONLY_FAIL_DRIVER = """
import sys
import time
import types

from reflex.utils import build, exec as exec_mod, telemetry


def fake_frontend(root, port, backend_present):
    time.sleep(0.5)
    raise RuntimeError("frontend exploded")


exec_mod.run_frontend = fake_frontend
telemetry.send = lambda *a, **k: None
build.setup_frontend = lambda *a, **k: None

import reflex.reflex as reflex_module

reflex_module._compile_app = lambda: None
reflex_module.get_config = lambda: types.SimpleNamespace(
    _set_persistent=lambda **k: None
)

from reflex_base import constants

reflex_module._run_dev(
    constants.RunningMode.FRONTEND_ONLY,
    frontend_port=3000,
    backend_port=None,
    backend_host="0.0.0.0",
)
"""


@pytest.mark.skipif(sys.platform == "win32", reason="signal semantics are POSIX")
def test_run_dev_frontend_only_task_failure_propagates(tmp_path):
    """A frontend task failure in frontend-only mode keeps its own error.

    The internal wake-up SIGINT must surface the task's exception (nonzero
    exit, original error text) instead of being converted into a clean
    SystemExit(0).
    """
    from reflex.testing import DEFAULT_TIMEOUT

    driver = tmp_path / "frontend_only_fail_driver.py"
    driver.write_text(_FRONTEND_ONLY_FAIL_DRIVER)
    proc = _run_driver(driver, DEFAULT_TIMEOUT)
    assert proc.returncode != 0, (
        f"frontend failure was masked as a clean exit: {proc.stdout}{proc.stderr}"
    )
    assert "frontend exploded" in proc.stderr, (
        f"original error lost: {proc.stdout}{proc.stderr}"
    )


_FRONTEND_ONLY_FAST_FAIL_DRIVER = """
import types

from reflex.utils import build, exec as exec_mod, telemetry


def fake_frontend(root, port, backend_present):
    raise RuntimeError("frontend exploded immediately")


exec_mod.run_frontend = fake_frontend
telemetry.send = lambda *a, **k: None
build.setup_frontend = lambda *a, **k: None

import reflex.reflex as reflex_module

reflex_module._compile_app = lambda: None
reflex_module.get_config = lambda: types.SimpleNamespace(
    _set_persistent=lambda **k: None
)

from reflex_base import constants

reflex_module._run_dev(
    constants.RunningMode.FRONTEND_ONLY,
    frontend_port=3000,
    backend_port=None,
    backend_host="0.0.0.0",
)
"""


@pytest.mark.skipif(sys.platform == "win32", reason="signal semantics are POSIX")
def test_run_dev_frontend_only_immediate_failure_never_masked(tmp_path):
    """A frontend that fails at spawn time must never exit cleanly either.

    The wake-up SIGINT can land before the run tasks are visible to the
    frontend-only signal handler; that early path must still surface the
    task's exception. Repeated runs smoke out the race.
    """
    from reflex.testing import DEFAULT_TIMEOUT

    driver = tmp_path / "frontend_only_fast_fail_driver.py"
    driver.write_text(_FRONTEND_ONLY_FAST_FAIL_DRIVER)
    for attempt in range(5):
        proc = _run_driver(driver, DEFAULT_TIMEOUT)
        assert proc.returncode != 0, (
            f"attempt {attempt}: immediate frontend failure was masked as a "
            f"clean exit: {proc.stdout}{proc.stderr}"
        )
        assert "frontend exploded immediately" in proc.stderr, (
            f"attempt {attempt}: original error lost: {proc.stdout}{proc.stderr}"
        )


_FRONTEND_ONLY_STARTUP_SIGNAL_DRIVER = """
import os
import sys
import types

CHILD_FILE = {child_file!r}
SIGNAL = {sig}

from reflex.utils import build, exec as exec_mod, processes, telemetry


def fake_frontend(root, port, backend_present):
    # Fire the signal while the run is still starting up, then spawn a
    # detached child so teardown has a tree to reap.
    os.kill(os.getpid(), SIGNAL)
    child = processes.new_process(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        run_managed=True,
        start_new_session=True,
    )
    with open(CHILD_FILE, "w") as f:
        f.write(str(child.pid))
    child.wait()


exec_mod.run_frontend = fake_frontend
telemetry.send = lambda *a, **k: None
build.setup_frontend = lambda *a, **k: None

import reflex.reflex as reflex_module

reflex_module._compile_app = lambda: None
reflex_module.get_config = lambda: types.SimpleNamespace(
    _set_persistent=lambda **k: None
)

from reflex_base import constants

reflex_module._run_dev(
    constants.RunningMode.FRONTEND_ONLY,
    frontend_port=3000,
    backend_port=None,
    backend_host="0.0.0.0",
)
"""


@pytest.mark.skipif(sys.platform == "win32", reason="signal semantics are POSIX")
@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT])
def test_run_dev_frontend_only_startup_signal_exits_cleanly(sig, tmp_path):
    """A genuine signal during startup still unwinds cleanly.

    Frontend-only mode disables the run context's internal failure wake-up
    (the main thread blocks on the frontend task's result, which propagates
    failures itself), so the frontend-only handlers only ever see real
    external signals. A SIGTERM/SIGINT landing before the run settles must
    exit 0 and reap the frontend tree - never a KeyboardInterrupt traceback.
    """
    from reflex.testing import DEFAULT_TIMEOUT

    driver = tmp_path / "startup_signal_driver.py"
    child_file = tmp_path / "child.pid"
    driver.write_text(
        _FRONTEND_ONLY_STARTUP_SIGNAL_DRIVER.format(
            child_file=str(child_file), sig=int(sig)
        )
    )
    proc = _run_driver(driver, DEFAULT_TIMEOUT, child_file)
    assert proc.returncode == 0, (
        f"early signal was not a clean exit (rc {proc.returncode}): "
        f"{proc.stdout}{proc.stderr}"
    )
    child_pid = int(child_file.read_text().strip())
    assert _pid_gone(child_pid), "frontend child survived a startup signal"
