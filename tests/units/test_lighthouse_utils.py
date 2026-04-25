"""Unit tests for Lighthouse benchmark utilities."""

import subprocess
from types import SimpleNamespace

import pytest

from tests.integration import lighthouse_utils


@pytest.fixture(autouse=True)
def clear_lighthouse_command_cache():
    """Reset cached Lighthouse command preparation between tests."""
    lighthouse_utils._prepare_lighthouse_command.cache_clear()
    yield
    lighthouse_utils._prepare_lighthouse_command.cache_clear()


def test_get_lighthouse_command_prefers_npx_before_pnpx(
    monkeypatch: pytest.MonkeyPatch,
):
    """Use npx first when both package runners are available."""
    monkeypatch.delenv(lighthouse_utils.LIGHTHOUSE_COMMAND_ENV_VAR, raising=False)
    monkeypatch.setattr(
        lighthouse_utils.shutil,
        "which",
        lambda command: {
            "npx": "/usr/bin/npx",
            "pnpx": "/usr/bin/pnpx",
        }.get(command),
    )

    assert lighthouse_utils.get_lighthouse_command() == [
        "npx",
        "--yes",
        lighthouse_utils.LIGHTHOUSE_CLI_PACKAGE,
    ]


def test_get_lighthouse_command_falls_back_to_pnpx(
    monkeypatch: pytest.MonkeyPatch,
):
    """Use pnpx when npx is unavailable."""
    monkeypatch.delenv(lighthouse_utils.LIGHTHOUSE_COMMAND_ENV_VAR, raising=False)
    monkeypatch.setattr(
        lighthouse_utils.shutil,
        "which",
        lambda command: {
            "pnpx": "/usr/bin/pnpx",
        }.get(command),
    )

    assert lighthouse_utils.get_lighthouse_command() == [
        "pnpx",
        lighthouse_utils.LIGHTHOUSE_CLI_PACKAGE,
    ]


def test_prepare_lighthouse_command_warms_package_runner_once(
    monkeypatch: pytest.MonkeyPatch,
):
    """Warm package-runner commands once before Lighthouse executes."""
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(command: list[str], **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(lighthouse_utils.subprocess, "run", fake_run)
    command = ("npx", "--yes", lighthouse_utils.LIGHTHOUSE_CLI_PACKAGE)

    assert lighthouse_utils._prepare_lighthouse_command(command) == command
    assert lighthouse_utils._prepare_lighthouse_command(command) == command

    assert calls == [
        (
            [*command, "--version"],
            {
                "check": True,
                "capture_output": True,
                "text": True,
                "timeout": lighthouse_utils.LIGHTHOUSE_COMMAND_PREP_TIMEOUT_SECONDS,
            },
        )
    ]


def test_prepare_lighthouse_command_timeout_has_friendly_message(
    monkeypatch: pytest.MonkeyPatch,
):
    """Timeouts during CLI warmup should fail with helpful pytest output."""

    def fake_run(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(
            cmd=["npx", "--yes", lighthouse_utils.LIGHTHOUSE_CLI_PACKAGE, "--version"],
            timeout=lighthouse_utils.LIGHTHOUSE_COMMAND_PREP_TIMEOUT_SECONDS,
            output="prep stdout",
            stderr="prep stderr",
        )

    monkeypatch.setattr(lighthouse_utils.subprocess, "run", fake_run)
    command = ("npx", "--yes", lighthouse_utils.LIGHTHOUSE_CLI_PACKAGE)

    with pytest.raises(pytest.fail.Exception, match="timed out after 300s"):
        lighthouse_utils._prepare_lighthouse_command(command)


def test_run_lighthouse_timeout_has_friendly_message(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Timeouts during a Lighthouse run should be reported via pytest.fail."""

    def fake_run(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(
            cmd=["lighthouse", "http://localhost:3000"],
            timeout=lighthouse_utils.LIGHTHOUSE_RUN_TIMEOUT_SECONDS,
            output="run stdout",
            stderr="run stderr",
        )

    monkeypatch.setattr(
        lighthouse_utils, "_prepare_lighthouse_command", lambda command: command
    )
    monkeypatch.setattr(
        lighthouse_utils, "get_lighthouse_command", lambda: ["lighthouse"]
    )
    monkeypatch.setattr(lighthouse_utils, "get_chrome_path", lambda: "/tmp/chrome")
    monkeypatch.setattr(lighthouse_utils.subprocess, "run", fake_run)

    with pytest.raises(pytest.fail.Exception, match="timed out after 300s"):
        lighthouse_utils.run_lighthouse(
            "http://localhost:3000", tmp_path / "lighthouse-report.json"
        )


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "http://0.0.0.0:3001/dashboard?tab=perf",
            "http://127.0.0.1:3001/dashboard?tab=perf",
        ),
        (
            "http://[::]:3001/dashboard?tab=perf",
            "http://[::1]:3001/dashboard?tab=perf",
        ),
        (
            "http://localhost:3001/dashboard?tab=perf",
            "http://localhost:3001/dashboard?tab=perf",
        ),
    ],
)
def test_get_lighthouse_target_url(url: str, expected: str):
    """Convert bind-all addresses into loopback addresses for browser clients."""
    assert lighthouse_utils._get_lighthouse_target_url(url) == expected
