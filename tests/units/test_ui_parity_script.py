"""Tests for scripts/ui_parity.py, the one command of the rx.ui parity harness."""

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
