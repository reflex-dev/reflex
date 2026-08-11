"""Tests for reflex_release.dist."""

from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path

import pytest
from packaging.version import Version
from reflex_release.actions import ReleaseError
from reflex_release.dist import dist_metadata_version, pin_exact, verify_dist

METADATA = "Metadata-Version: 2.4\nName: widget-core\nVersion: {version}\n\nBody text\n"


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
            f"{name}-{version}.dist-info/METADATA", METADATA.format(version=version)
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
    pkg_info.write_text(METADATA.format(version=version))
    with tarfile.open(path, "w:gz") as sdist:
        sdist.add(pkg_info, arcname=f"{name}-{version}/PKG-INFO")
    pkg_info.unlink()
    return path


def test_dist_metadata_version(tmp_path: Path) -> None:
    assert dist_metadata_version(make_wheel(tmp_path, "1.2.3")) == "1.2.3"
    assert dist_metadata_version(make_sdist(tmp_path, "1.2.3")) == "1.2.3"


def test_dist_metadata_version_rejects_other_files(tmp_path: Path) -> None:
    stray = tmp_path / "notes.txt"
    stray.write_text("x")
    with pytest.raises(ReleaseError, match="unexpected artifact type"):
        dist_metadata_version(stray)


def test_verify_dist_accepts_matching_artifacts(tmp_path: Path) -> None:
    make_wheel(tmp_path, "1.2.3")
    make_sdist(tmp_path, "1.2.3")
    assert verify_dist(tmp_path, Version("1.2.3")) == 2


def test_verify_dist_rejects_a_mismatch(tmp_path: Path) -> None:
    make_wheel(tmp_path, "0.0.0")
    with pytest.raises(ReleaseError, match=r"has version 0\.0\.0, expected 1\.2\.3"):
        verify_dist(tmp_path, Version("1.2.3"))


def test_verify_dist_ignores_hidden_files(tmp_path: Path) -> None:
    make_wheel(tmp_path, "1.2.3")
    (tmp_path / ".gitignore").write_text("*\n")
    assert verify_dist(tmp_path, Version("1.2.3")) == 1


def test_verify_dist_requires_artifacts(tmp_path: Path) -> None:
    with pytest.raises(ReleaseError, match="no artifacts"):
        verify_dist(tmp_path, Version("1.2.3"))


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
        f'[project]\ndependencies = [{requirement}, "requests >= 2"]\n'
    )
    pin_exact(pyproject, "widget-core", Version("1.2.3"))
    assert pyproject.read_text() == (
        f'[project]\ndependencies = [{expected}, "requests >= 2"]\n'
    )


def test_pin_exact_ignores_similar_names(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\ndependencies = ["widget-core-extras >= 1", "widget-core >= 0.1.0"]\n'
    )
    pin_exact(pyproject, "widget-core", Version("1.2.3"))
    assert '"widget-core-extras >= 1"' in pyproject.read_text()
    assert '"widget-core == 1.2.3"' in pyproject.read_text()


@pytest.mark.parametrize(
    "dependencies",
    ['["requests >= 2"]', '["widget-core >= 1", "widget-core >= 2"]'],
)
def test_pin_exact_requires_exactly_one_match(
    tmp_path: Path, dependencies: str
) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(f"[project]\ndependencies = {dependencies}\n")
    with pytest.raises(ReleaseError, match="expected exactly one"):
        pin_exact(pyproject, "widget-core", Version("1.2.3"))
