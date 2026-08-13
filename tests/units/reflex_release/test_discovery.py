"""Tests for reflex_release.discovery."""

from __future__ import annotations

from pathlib import Path

import pytest
from reflex_release.actions import ReleaseError
from reflex_release.changelog import DEFAULT_TITLE_FORMAT
from reflex_release.config import Config, load_config
from reflex_release.discovery import title_format


def set_title_format(repo: Path, value: str) -> Config:
    """Replace the repository's towncrier ``title_format`` setting.

    Args:
        repo: The repository root.
        value: The TOML value to write, verbatim.

    Returns:
        The reloaded configuration.
    """
    pyproject = repo / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    start = text.index("title_format = ")
    end = text.index("\n", start)
    pyproject.write_text(
        text[:start] + f"title_format = {value}" + text[end:], encoding="utf-8"
    )
    return load_config(repo)


def test_title_format_defaults_when_unset(config: Config, repo: Path) -> None:
    assert title_format(set_title_format(repo, '""')) == DEFAULT_TITLE_FORMAT


def test_title_format_rejects_a_disabled_heading(config: Config, repo: Path) -> None:
    """A `title_format = false` writes towncrier sections with no version heading."""
    reloaded = set_title_format(repo, "false")
    with pytest.raises(ReleaseError, match="no version heading"):
        title_format(reloaded)


def test_title_format_rejects_a_non_string(config: Config, repo: Path) -> None:
    reloaded = set_title_format(repo, "3")
    with pytest.raises(ReleaseError, match="must be a string"):
        title_format(reloaded)
