"""Tests for scripts/ui_parity.py, the one command of the rx.ui parity harness."""

import subprocess
import sys

import pytest
from ui_parity import allowlist

from scripts import ui_parity

TESTS = "tests/integration/tests_playwright/test_ui_parity.py"


def test_pytest_command_runs_everything_in_one_engine_by_default():
    assert ui_parity.pytest_command([], ["chromium"], []) == [
        sys.executable,
        "-m",
        "pytest",
        TESTS,
        "-rs",
        "--browser",
        "chromium",
    ]


def test_pytest_command_selects_components_and_engines():
    assert ui_parity.pytest_command(
        ["box", "button"], ["chromium", "firefox", "webkit"], ["-x"]
    ) == [
        sys.executable,
        "-m",
        "pytest",
        TESTS,
        "-rs",
        "--browser",
        "chromium",
        "--browser",
        "firefox",
        "--browser",
        "webkit",
        "-k",
        "test_run_time or -box] or -box- or -button] or -button-",
        "-x",
    ]


def test_differences_prints_the_allowlist(capsys: pytest.CaptureFixture[str]):
    assert ui_parity.main(["differences"]) == 0
    assert capsys.readouterr().out == (
        allowlist.differences_markdown(allowlist.load()) + "\n"
    )


def test_fonts_reach_the_tests_through_the_environment(
    monkeypatch: pytest.MonkeyPatch,
):
    """``--fonts`` names the two families in the variable the tests read."""
    runs = []

    def run(command, *, cwd, env, check):
        runs.append((command, cwd, env.get("UI_PARITY_FONTS"), check))
        return subprocess.CompletedProcess(command, 3)

    monkeypatch.delenv("UI_PARITY_FONTS", raising=False)
    monkeypatch.setattr(ui_parity.subprocess, "run", run)
    assert ui_parity.main(["link", "--fonts", "DejaVu Sans", "Liberation Mono"]) == 3
    assert ui_parity.main(["link"]) == 3
    command = ui_parity.pytest_command(["link"], ["chromium"], [])
    assert runs == [
        (command, ui_parity.REPO_ROOT, "DejaVu Sans|Liberation Mono", False),
        (command, ui_parity.REPO_ROOT, None, False),
    ]
