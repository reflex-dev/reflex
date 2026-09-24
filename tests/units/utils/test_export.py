"""Tests for reflex.utils.export."""

from __future__ import annotations

import multiprocessing
import os
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from pytest_mock import MockerFixture
from reflex_base import constants

from reflex.utils import build_cache, export


@pytest.fixture
def patched_export(mocker: MockerFixture) -> dict:
    """Patch out side-effecting dependencies of ``export.export()``.

    Returns:
        Dict of patched mocks keyed by short name.
    """
    return {
        "frontend_build_lock": mocker.patch(
            "reflex.utils.build_cache.frontend_build_lock"
        ),
        "get_compiled_app": mocker.patch(
            "reflex.utils.export.prerequisites.get_compiled_app"
        ),
        "setup_frontend": mocker.patch("reflex.utils.export.build.setup_frontend"),
        "build": mocker.patch("reflex.utils.export.build.build"),
        "zip_app": mocker.patch("reflex.utils.export.build.zip_app"),
        "send": mocker.patch("reflex.utils.export.telemetry.send"),
        "output_system_info": mocker.patch(
            "reflex.utils.export.exec.output_system_info"
        ),
        "env_mode_set": mocker.patch(
            "reflex.utils.export.environment.REFLEX_ENV_MODE"
        ).set,
        "get_config": mocker.patch(
            "reflex.utils.export.get_config", return_value=mocker.Mock()
        ),
    }


def _send_kwargs(send_mock) -> dict:
    """Extract kwargs from the single telemetry.send call.

    Returns:
        The kwargs dict from the recorded call.
    """
    assert send_mock.call_count == 1
    return send_mock.call_args.kwargs


def test_export_success_emits_success_event_with_all_phase_durations(patched_export):
    export.export()

    kwargs = _send_kwargs(patched_export["send"])
    assert kwargs["status"] == "success"
    assert isinstance(kwargs["duration"], float)
    assert isinstance(kwargs["compile_duration"], float)
    assert isinstance(kwargs["setup_duration"], float)
    assert isinstance(kwargs["build_duration"], float)
    assert isinstance(kwargs["zip_duration"], float)
    assert kwargs["detail"] is None


@pytest.mark.parametrize(
    ("failing_target", "expected_present", "expected_absent"),
    [
        (
            "get_compiled_app",
            {"compile_duration"},
            {"setup_duration", "build_duration", "zip_duration"},
        ),
        (
            "setup_frontend",
            {"compile_duration", "setup_duration"},
            {"build_duration", "zip_duration"},
        ),
        (
            "build",
            {"compile_duration", "setup_duration", "build_duration"},
            {"zip_duration"},
        ),
        (
            "zip_app",
            {"compile_duration", "setup_duration", "build_duration", "zip_duration"},
            set(),
        ),
    ],
)
def test_export_failure_emits_failure_event_with_partial_phase_durations(
    patched_export,
    failing_target: str,
    expected_present: set[str],
    expected_absent: set[str],
):
    patched_export[failing_target].side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        export.export()

    kwargs = _send_kwargs(patched_export["send"])
    assert kwargs["status"] == "failure"
    assert kwargs["detail"] == "RuntimeError"
    assert isinstance(kwargs["duration"], float)
    for key in expected_present:
        assert isinstance(kwargs[key], float), (
            f"expected {key} to carry a float duration"
        )
    for key in expected_absent:
        assert kwargs[key] is None, f"expected {key} to be None (phase did not run)"


def test_export_backend_only_emits_only_zip_duration(patched_export):
    export.export(frontend=False, zipping=True)

    kwargs = _send_kwargs(patched_export["send"])
    assert kwargs["status"] == "success"
    assert kwargs["compile_duration"] is None
    assert kwargs["setup_duration"] is None
    assert kwargs["build_duration"] is None
    assert isinstance(kwargs["zip_duration"], float)


def test_export_no_zip_emits_only_compile_and_build_durations(patched_export):
    export.export(frontend=True, zipping=False)

    kwargs = _send_kwargs(patched_export["send"])
    assert kwargs["status"] == "success"
    assert isinstance(kwargs["compile_duration"], float)
    assert isinstance(kwargs["setup_duration"], float)
    assert isinstance(kwargs["build_duration"], float)
    assert kwargs["zip_duration"] is None


@pytest.mark.parametrize(
    ("frontend", "zipping", "phases"),
    [
        (True, True, ["get_compiled_app", "setup_frontend", "build", "zip_app"]),
        (True, False, ["get_compiled_app", "setup_frontend", "build"]),
    ],
)
def test_export_holds_frontend_lock_through_packaging(
    patched_export, frontend: bool, zipping: bool, phases: list[str]
):
    """Generated inputs and both archives belong to one locked export."""
    lock = patched_export["frontend_build_lock"]
    context = lock.return_value

    def require_lock(*args, **kwargs):
        """Require each export phase to run before the lock is released."""
        context.__enter__.assert_called_once()
        context.__exit__.assert_not_called()

    for phase in phases:
        patched_export[phase].side_effect = require_lock
    patched_export["env_mode_set"].side_effect = require_lock
    config = patched_export["get_config"].return_value
    config._set_persistent.side_effect = require_lock

    export.export(
        frontend=frontend,
        zipping=zipping,
        api_url="https://api.example.com",
        deploy_url="https://app.example.com",
    )

    lock.assert_called_once_with(export.prerequisites.get_web_dir())
    context.__exit__.assert_called_once_with(None, None, None)
    assert config._set_persistent.call_count == 2


@pytest.mark.parametrize(
    ("workspace_exists", "backend", "zipping", "needs_lock"),
    [
        (False, True, True, False),
        (True, True, True, True),
        (True, False, True, False),
        (True, True, False, False),
    ],
)
def test_backend_only_export_locks_existing_workspace_for_packaging(
    patched_export, tmp_path, mocker, workspace_exists, backend, zipping, needs_lock
):
    """Backend packaging locks existing generated files without creating a workspace."""
    web = tmp_path / ".web"
    if workspace_exists:
        web.mkdir()
    mocker.patch.object(export.prerequisites, "get_web_dir", return_value=web)

    export.export(frontend=False, backend=backend, zipping=zipping)

    lock = patched_export["frontend_build_lock"]
    if needs_lock:
        lock.assert_called_once_with(web)
        lock.return_value.__exit__.assert_called_once_with(None, None, None)
    else:
        lock.assert_not_called()
    assert web.exists() == workspace_exists


def _export_backend_in_process(root: Path, attempted, finished):
    """Create a real backend archive from an independent interpreter.

    Args:
        root: The application root containing the shared frontend workspace.
        attempted: Event set immediately before exporting.
        finished: Event set after the backend archive has been written.
    """
    os.chdir(root)
    with (
        patch.object(export.prerequisites, "get_web_dir", return_value=root / ".web"),
        patch.object(export, "get_config", return_value=Mock()),
        patch.object(export.exec, "output_system_info"),
        patch.object(export.telemetry, "send"),
    ):
        attempted.set()
        export.export(frontend=False, zip_dest_dir=str(root))
        finished.set()


@pytest.mark.parametrize("cache_enabled", ["true", "false"])
def test_backend_archive_waits_for_frontend_compilation(
    tmp_path, monkeypatch, cache_enabled
):
    """Backend ZIPs wait for the compiler to publish its temporary stateful marker."""
    monkeypatch.setenv("REFLEX_FRONTEND_BUILD_CACHE", cache_enabled)
    web = tmp_path / ".web"
    backend = web / constants.Dirs.BACKEND
    backend.mkdir(parents=True)
    marker = backend / constants.Dirs.STATEFUL_PAGES
    marker.write_text('["old"]')
    temporary = marker.with_suffix(".tmp")
    temporary.write_text('["new"]')
    (tmp_path / "app.py").write_text("# Backend source\n", newline="\r\n")
    context = multiprocessing.get_context("spawn")
    attempted, finished = context.Event(), context.Event()
    child = context.Process(
        target=_export_backend_in_process, args=(tmp_path, attempted, finished)
    )
    try:
        with build_cache.frontend_build_lock(web):
            child.start()
            assert attempted.wait(15)
            assert not finished.wait(0.5), "Backend ZIP raced with frontend compilation"
            temporary.replace(marker)
        assert finished.wait(15)
    finally:
        if child.pid is not None:
            child.join(15)
            if child.is_alive():
                child.terminate()
                child.join(5)
    assert child.exitcode == 0

    with zipfile.ZipFile(tmp_path / constants.ComponentName.BACKEND.zip()) as archive:
        assert archive.read(marker.relative_to(tmp_path).as_posix()) == b'["new"]'
        assert temporary.relative_to(tmp_path).as_posix() not in archive.namelist()
        assert archive.read("app.py") == (tmp_path / "app.py").read_bytes()


@pytest.mark.parametrize(
    "failing_target", ["get_compiled_app", "setup_frontend", "build", "zip_app"]
)
def test_export_releases_frontend_lock_before_failure_telemetry(
    patched_export, failing_target: str
):
    """A failed export releases shared files before reporting its failure."""
    context = patched_export["frontend_build_lock"].return_value
    error = RuntimeError("export failed")
    patched_export[failing_target].side_effect = error

    def require_release(*args, **kwargs):
        """Telemetry runs outside the frontend lock even on failure."""
        context.__enter__.assert_called_once()
        context.__exit__.assert_called_once()

    patched_export["send"].side_effect = require_release
    with pytest.raises(RuntimeError, match="export failed"):
        export.export()

    assert context.__exit__.call_args.args[:2] == (RuntimeError, error)
