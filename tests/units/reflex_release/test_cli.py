"""Tests for the reflex_release command line interface."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from reflex_release.cli import find_root, main

Outputs = Callable[[], dict[str, str]]


def test_find_root_walks_up_to_the_pyproject(repo: Path) -> None:
    nested = repo / "src" / "mypkg"
    assert find_root(nested) == repo


def test_find_root_falls_back_to_the_starting_point(tmp_path: Path) -> None:
    assert find_root(tmp_path) == tmp_path


def test_detect_reads_options_from_the_environment(
    repo: Path, outputs: Outputs, monkeypatch: pytest.MonkeyPatch
) -> None:
    (repo / "CHANGELOG.md").write_text(
        "## v1.0.0 (2026-01-01)\n\nNo significant changes.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("REF_NAME", "main")
    # The parser reads its defaults at build time, so the environment must be
    # set before main() constructs it — which is how the workflows invoke it.
    assert main(["--root", str(repo), "detect"]) == 0
    assert json.loads(outputs()["packages"])[0]["package"] == "mypkg"


def test_flags_win_over_the_environment(
    repo: Path, outputs: Outputs, monkeypatch: pytest.MonkeyPatch
) -> None:
    (repo / "CHANGELOG.md").write_text(
        "## v1.0.0 (2026-01-01)\n\nNo significant changes.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("REF_NAME", "main")
    assert main(["--root", str(repo), "detect", "--ref-name", "feature/x"]) == 0
    assert outputs()["any"] == "false"


def test_failures_exit_non_zero_with_a_message(
    repo: Path, outputs: Outputs, capsys: pytest.CaptureFixture
) -> None:
    assert main(["--root", str(repo), "plan", "--action", "nope"]) == 1
    assert "Error: unknown action" in capsys.readouterr().err


def test_packages_command(repo: Path, capsys: pytest.CaptureFixture) -> None:
    assert main(["--root", str(repo), "packages"]) == 0
    assert capsys.readouterr().out.split() == ["mypkg", "widget-core"]


def test_create_makes_a_fragment_for_the_root_package(repo: Path) -> None:
    assert main(["--root", str(repo), "create", "42.feature.md"]) == 0
    assert (repo / "news" / "42.feature.md").is_file()


def test_create_targets_a_sub_package(repo: Path) -> None:
    assert (
        main(["--root", str(repo), "create", "--package", "widget-core", "7.bugfix.md"])
        == 0
    )
    assert (repo / "packages" / "widget-core" / "news" / "7.bugfix.md").is_file()


def test_sync_check_reports_missing_workflows(
    repo: Path, capsys: pytest.CaptureFixture
) -> None:
    assert main(["--root", str(repo), "sync", "--check"]) == 1
    assert "out of date" in capsys.readouterr().err


def test_init_then_sync_check_passes(tmp_path: Path) -> None:
    (tmp_path / "src" / "solo").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "solo"\n', encoding="utf-8"
    )
    assert main(["--root", str(tmp_path), "init", "--pin", "1.0.0"]) == 0
    assert main(["--root", str(tmp_path), "sync", "--check"]) == 0


def test_init_unpinned(tmp_path: Path) -> None:
    (tmp_path / "src" / "solo").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "solo"\n', encoding="utf-8"
    )
    assert main(["--root", str(tmp_path), "init", "--pin", "none"]) == 0
    assert 'cli-command = "uvx reflex-release"' in (
        tmp_path / "pyproject.toml"
    ).read_text(encoding="utf-8")
