"""Tests for reflex.utils.export."""

from __future__ import annotations

import pytest
from pytest_mock import MockerFixture

from reflex.utils import export


@pytest.fixture
def patched_export(mocker: MockerFixture) -> dict:
    """Patch out side-effecting dependencies of ``export.export()``.

    Args:
        mocker: pytest-mock fixture.

    Returns:
        Dict of patched mocks keyed by short name.
    """
    return {
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
        "console_rule": mocker.patch("reflex.utils.export.console.rule"),
        "set_log_level": mocker.patch("reflex.utils.export.console.set_log_level"),
        "env_mode_set": mocker.patch(
            "reflex.utils.export.environment.REFLEX_ENV_MODE.set"
        ),
        "get_config": mocker.patch(
            "reflex.utils.export.get_config", return_value=mocker.Mock()
        ),
    }


def _send_kwargs(send_mock) -> dict:
    """Extract kwargs from the single telemetry.send call.

    Args:
        send_mock: Mock for ``telemetry.send``; must have been called exactly once with positional ``"export"``.

    Returns:
        The kwargs dict from the recorded call.
    """
    assert send_mock.call_count == 1
    args, kwargs = send_mock.call_args
    assert args == ("export",)
    return kwargs


def test_export_success_emits_success_event_with_all_phase_durations(patched_export):
    export.export()

    kwargs = _send_kwargs(patched_export["send"])
    assert kwargs["status"] == "success"
    assert isinstance(kwargs["duration"], float)
    assert kwargs["duration"] >= 0
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
