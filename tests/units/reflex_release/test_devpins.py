"""Tests for reflex_release.devpins."""

from __future__ import annotations

from pathlib import Path

import pytest
from reflex_release.actions import ReleaseError
from reflex_release.config import Config
from reflex_release.devpins import (
    check_dev_pins,
    parse_requirement,
    published_dependencies,
)


@pytest.mark.parametrize(
    ("requirement", "expected"),
    [
        ("widget-core >= 0.1.0", ("widget-core", False)),
        ("widget-core >= 0.1.0.dev1", ("widget-core", True)),
        ("widget-core == 1.0.dev3", ("widget-core", True)),
        ("widget-core ~= 1.0.dev3", ("widget-core", True)),
        # An upper bound or exclusion on a dev release stays resolvable.
        ("widget-core >= 1, != 2.0.dev1", ("widget-core", False)),
        ("widget-core < 2.0.dev1", ("widget-core", False)),
        ("widget-core == 1.2.*", ("widget-core", False)),
        ("Widget_Core[extra] >= 1; python_version > '3.10'", ("widget-core", False)),
        ("not a requirement !!", ("", False)),
    ],
)
def test_parse_requirement(requirement: str, expected: tuple[str, bool]) -> None:
    assert parse_requirement(requirement) == expected


def test_published_dependencies_includes_extras_but_not_groups() -> None:
    project = {
        "dependencies": ["a >= 1"],
        "optional-dependencies": {"extra": ["b >= 2"]},
        "dependency-groups": {"dev": ["c >= 3"]},
    }
    assert published_dependencies(project) == ["a >= 1", "b >= 2"]


def test_check_dev_pins_accepts_published_pins(
    config: Config, capsys: pytest.CaptureFixture
) -> None:
    check_dev_pins(config, [])
    assert "No development-release dependency pins" in capsys.readouterr().out


def test_check_dev_pins_rejects_a_dev_pin(config: Config, repo: Path) -> None:
    pyproject = repo / "pyproject.toml"
    pyproject.write_text(pyproject.read_text().replace(">= 0.1.0", ">= 0.2.0.dev1"))
    with pytest.raises(ReleaseError, match="must not be published"):
        check_dev_pins(config, [])


def test_check_dev_pins_is_scoped_to_the_selected_package(
    config: Config, repo: Path
) -> None:
    pyproject = repo / "pyproject.toml"
    pyproject.write_text(pyproject.read_text().replace(">= 0.1.0", ">= 0.2.0.dev1"))
    # The sibling can still be released while its dependent dev-pins it.
    check_dev_pins(config, ["widget-core"])
    with pytest.raises(ReleaseError, match="must not be published"):
        check_dev_pins(config, ["mypkg"])


def test_check_dev_pins_rejects_unknown_packages(config: Config) -> None:
    with pytest.raises(ReleaseError, match="unknown package"):
        check_dev_pins(config, ["ghost"])
