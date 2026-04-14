"""Unit tests for Lighthouse benchmark utilities."""

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
