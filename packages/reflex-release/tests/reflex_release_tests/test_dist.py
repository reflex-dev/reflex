"""Tests for reflex_release.dist."""

from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path

import pytest
from packaging.version import Version
from reflex_release.actions import ReleaseError
from reflex_release.dist import dist_metadata, normalize_name, pin_exact, verify_dist

METADATA = "Metadata-Version: 2.4\nName: {name}\nVersion: {version}\n\nBody text\n"


def make_wheel(directory: Path, version: str, name: str = "widget_core") -> Path:
    """Write a minimal wheel carrying core metadata.

    Args:
        directory: Where to write the wheel.
        version: The version to declare.
        name: The distribution's normalized name.

    Returns:
        The wheel path.
    """
    path = directory / f"{name}-{version}-py3-none-any.whl"
    with zipfile.ZipFile(path, "w") as wheel:
        wheel.writestr(
            f"{name}-{version}.dist-info/METADATA",
            METADATA.format(name=name, version=version),
        )
    return path


def make_sdist(directory: Path, version: str, name: str = "widget_core") -> Path:
    """Write a minimal sdist carrying core metadata.

    Args:
        directory: Where to write the sdist.
        version: The version to declare.
        name: The distribution's normalized name.

    Returns:
        The sdist path.
    """
    path = directory / f"{name}-{version}.tar.gz"
    pkg_info = directory / "PKG-INFO"
    pkg_info.write_text(METADATA.format(name=name, version=version), encoding="utf-8")
    with tarfile.open(path, "w:gz") as sdist:
        sdist.add(pkg_info, arcname=f"{name}-{version}/PKG-INFO")
    pkg_info.unlink()
    return path


def test_dist_metadata(tmp_path: Path) -> None:
    assert dist_metadata(make_wheel(tmp_path, "1.2.3")) == ("widget_core", "1.2.3")
    assert dist_metadata(make_sdist(tmp_path, "1.2.3")) == ("widget_core", "1.2.3")


def test_dist_metadata_rejects_other_files(tmp_path: Path) -> None:
    stray = tmp_path / "notes.txt"
    stray.write_text("x", encoding="utf-8")
    with pytest.raises(ReleaseError, match="unexpected artifact type"):
        dist_metadata(stray)


def test_normalize_name() -> None:
    assert (
        normalize_name("Widget__Core") == normalize_name("widget.core") == "widget-core"
    )


def test_verify_dist_accepts_matching_artifacts(tmp_path: Path) -> None:
    make_wheel(tmp_path, "1.2.3")
    make_sdist(tmp_path, "1.2.3")
    # The metadata name and the expected name differ only by PEP 503 spelling.
    assert verify_dist(tmp_path, "widget-core", Version("1.2.3")) == 2


def test_verify_dist_rejects_a_mismatch(tmp_path: Path) -> None:
    make_wheel(tmp_path, "0.0.0")
    with pytest.raises(ReleaseError, match=r"has version 0\.0\.0, expected 1\.2\.3"):
        verify_dist(tmp_path, "widget-core", Version("1.2.3"))


def test_verify_dist_rejects_another_distribution(tmp_path: Path) -> None:
    """A lockstep sibling shares the version, so the name is what tells them apart."""
    make_wheel(tmp_path, "1.2.3", name="gadget_core")
    with pytest.raises(ReleaseError, match="is gadget_core, expected widget-core"):
        verify_dist(tmp_path, "widget-core", Version("1.2.3"))


def test_verify_dist_ignores_hidden_files(tmp_path: Path) -> None:
    make_wheel(tmp_path, "1.2.3")
    (tmp_path / ".gitignore").write_text("*\n", encoding="utf-8")
    assert verify_dist(tmp_path, "widget-core", Version("1.2.3")) == 1


def test_verify_dist_requires_artifacts(tmp_path: Path) -> None:
    with pytest.raises(ReleaseError, match="no artifacts"):
        verify_dist(tmp_path, "widget-core", Version("1.2.3"))


@pytest.mark.parametrize(
    ("requirement", "expected"),
    [
        ('"widget-core >= 0.1.0"', '"widget-core == 1.2.3"'),
        ('"widget-core>=0.1.0,<2"', '"widget-core == 1.2.3"'),
        ('"widget_core >= 0.1.0"', '"widget-core == 1.2.3"'),
        ('"widget-core[extra] >= 0.1.0"', '"widget-core[extra] == 1.2.3"'),
        # PEP 503 collapses any run of -, _ and . to one separator.
        ('"widget.core >= 0.1.0"', '"widget-core == 1.2.3"'),
        ('"Widget__Core >= 0.1.0"', '"widget-core == 1.2.3"'),
    ],
)
def test_pin_exact(tmp_path: Path, requirement: str, expected: str) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        f'[project]\ndependencies = [{requirement}, "requests >= 2"]\n',
        encoding="utf-8",
    )
    pin_exact(pyproject, "widget-core", Version("1.2.3"))
    assert pyproject.read_text(encoding="utf-8") == (
        f'[project]\ndependencies = [{expected}, "requests >= 2"]\n'
    )


def test_pin_exact_ignores_similar_names(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\ndependencies = ["widget-core-extras >= 1", "widget-core >= 0.1.0"]\n',
        encoding="utf-8",
    )
    pin_exact(pyproject, "widget-core", Version("1.2.3"))
    assert '"widget-core-extras >= 1"' in pyproject.read_text(encoding="utf-8")
    assert '"widget-core == 1.2.3"' in pyproject.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "dependencies",
    ['["requests >= 2"]', '["widget-core >= 1", "widget-core >= 2"]'],
)
def test_pin_exact_requires_exactly_one_match(
    tmp_path: Path, dependencies: str
) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        f"[project]\ndependencies = {dependencies}\n", encoding="utf-8"
    )
    with pytest.raises(ReleaseError, match="expected exactly one"):
        pin_exact(pyproject, "widget-core", Version("1.2.3"))


def test_expected_artifact_patterns_must_all_match(tmp_path: Path) -> None:
    """A platform matrix is only complete if every leg contributed a file."""
    make_wheel(tmp_path, "1.2.3")
    make_sdist(tmp_path, "1.2.3")
    assert (
        verify_dist(
            tmp_path,
            "widget-core",
            Version("1.2.3"),
            ["*.tar.gz", "*-py3-none-any.whl"],
        )
        == 2
    )


def test_a_missing_expected_artifact_stops_the_release(tmp_path: Path) -> None:
    """A matrix leg that produced nothing must not publish a partial set."""
    make_wheel(tmp_path, "1.2.3")
    with pytest.raises(ReleaseError, match=r"\*macosx\*\.whl"):
        verify_dist(tmp_path, "widget-core", Version("1.2.3"), ["*macosx*.whl"])
