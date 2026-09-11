"""Unit tests for scripts/verify_pyi.py (the published-artifact .pyi stub check)."""

import io
import sys
import tarfile
import zipfile
from collections.abc import Sequence
from pathlib import Path

import pytest

if sys.version_info < (3, 11):
    pytest.importorskip("tomli", reason="verify_pyi requires tomli on Python < 3.11")

from scripts import verify_pyi

REPO_ROOT = Path(__file__).resolve().parents[2]


def write_pyproject(package_dir: Path, build_table: str) -> Path:
    """Write a pyproject declaring the given [tool.hatch.build] body.

    Args:
        package_dir: Directory to write the pyproject into.
        build_table: The body of the package's [tool.hatch.build] table.

    Returns:
        The package directory.
    """
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "pyproject.toml").write_text(
        f'[project]\nname = "pkg"\nversion = "1.0"\n\n{build_table}\n'
    )
    return package_dir


def make_wheel(path: Path, names: Sequence[str]) -> Path:
    """Write a wheel containing empty members with the given names.

    Args:
        path: Where to write the wheel.
        names: Archive member names.

    Returns:
        The wheel path.
    """
    with zipfile.ZipFile(path, "w") as wheel:
        for name in names:
            wheel.writestr(name, "")
    return path


def make_sdist(path: Path, names: Sequence[str]) -> Path:
    """Write an sdist containing empty members with the given names.

    Args:
        path: Where to write the sdist.
        names: Archive member names.

    Returns:
        The sdist path.
    """
    with tarfile.open(path, "w:gz") as sdist:
        for name in names:
            sdist.addfile(tarfile.TarInfo(name), io.BytesIO(b""))
    return path


def run_main(monkeypatch: pytest.MonkeyPatch, build_dir: Path, dist_dir: Path) -> int:
    """Run verify_pyi.main with the hook's environment set.

    Args:
        monkeypatch: The fixture used to set the environment.
        build_dir: The package directory holding pyproject.toml.
        dist_dir: The directory holding the built artifacts.

    Returns:
        The exit code.
    """
    monkeypatch.setenv("PACKAGE", "pkg")
    monkeypatch.setenv("BUILD_DIR", str(build_dir))
    monkeypatch.setenv("DIST_DIR", str(dist_dir))
    return verify_pyi.main()


def test_generates_stubs_from_hook():
    assert verify_pyi.generates_stubs({"hooks": {"reflex-pyi": {}}})


def test_generates_stubs_from_artifacts():
    assert verify_pyi.generates_stubs({"targets": {"wheel": {"artifacts": ["*.pyi"]}}})


def test_generates_stubs_from_sdist_artifacts_only():
    assert verify_pyi.generates_stubs({
        "targets": {"sdist": {"artifacts": ["*.json", "*.pyi"]}}
    })


def test_generates_stubs_from_top_level_artifacts():
    assert verify_pyi.generates_stubs({"artifacts": ["/reflex/**/*.pyi"]})


def test_generates_stubs_from_target_hook():
    assert verify_pyi.generates_stubs({
        "targets": {"wheel": {"hooks": {"reflex-pyi": {}}}}
    })


def test_generates_stubs_ignores_unrelated_hooks_and_artifacts():
    assert not verify_pyi.generates_stubs({
        "hooks": {"custom": {"path": "scripts/other_build.py"}},
        "targets": {"wheel": {"artifacts": ["*.json"]}},
    })


def test_generates_stubs_without_build_table():
    assert not verify_pyi.generates_stubs({})


def test_build_table_reads_nested_table(tmp_path: Path):
    package = write_pyproject(
        tmp_path, "[tool.hatch.build]\ntargets.wheel.artifacts = ['*.pyi']"
    )
    assert verify_pyi.build_table(package) == {
        "targets": {"wheel": {"artifacts": ["*.pyi"]}}
    }


def test_build_table_without_hatch_config(tmp_path: Path):
    assert verify_pyi.build_table(write_pyproject(tmp_path, "")) == {}


def test_stub_count_wheel(tmp_path: Path):
    wheel = make_wheel(
        tmp_path / "pkg-1.0-py3-none-any.whl",
        ["pkg/__init__.py", "pkg/a.pyi", "pkg/b.pyi"],
    )
    assert verify_pyi.stub_count(wheel) == 2


def test_stub_count_wheel_without_stubs(tmp_path: Path):
    wheel = make_wheel(tmp_path / "pkg-1.0-py3-none-any.whl", ["pkg/__init__.py"])
    assert verify_pyi.stub_count(wheel) == 0


def test_stub_count_sdist(tmp_path: Path):
    sdist = make_sdist(
        tmp_path / "pkg-1.0.tar.gz", ["pkg-1.0/pkg/__init__.py", "pkg-1.0/pkg/a.pyi"]
    )
    assert verify_pyi.stub_count(sdist) == 1


def test_main_skips_package_that_generates_no_stubs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    build_dir = write_pyproject(tmp_path / "pkg", "")
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    make_wheel(dist_dir / "pkg-1.0-py3-none-any.whl", ["pkg/__init__.py"])
    assert run_main(monkeypatch, build_dir, dist_dir) == 0


def test_main_accepts_stubs_in_every_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    build_dir = write_pyproject(
        tmp_path / "pkg", "[tool.hatch.build.hooks.reflex-pyi]\ndependencies = []"
    )
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    make_wheel(dist_dir / "pkg-1.0-py3-none-any.whl", ["pkg/a.pyi"])
    make_sdist(dist_dir / "pkg-1.0.tar.gz", ["pkg-1.0/pkg/a.pyi"])
    assert run_main(monkeypatch, build_dir, dist_dir) == 0


def test_main_rejects_artifact_without_stubs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    build_dir = write_pyproject(
        tmp_path / "pkg", "[tool.hatch.build.hooks.reflex-pyi]\ndependencies = []"
    )
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    make_wheel(dist_dir / "pkg-1.0-py3-none-any.whl", ["pkg/__init__.py"])
    assert run_main(monkeypatch, build_dir, dist_dir) == 1
    assert "pkg-1.0-py3-none-any.whl" in capsys.readouterr().out


def test_main_rejects_a_single_artifact_missing_stubs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """One bad leg of a build matrix must fail even when its siblings are fine."""
    build_dir = write_pyproject(
        tmp_path / "pkg", "[tool.hatch.build.hooks.reflex-pyi]\ndependencies = []"
    )
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    make_wheel(dist_dir / "pkg-1.0-cp313-macosx.whl", ["pkg/a.pyi"])
    make_wheel(dist_dir / "pkg-1.0-cp313-linux.whl", ["pkg/__init__.py"])
    assert run_main(monkeypatch, build_dir, dist_dir) == 1
    out = capsys.readouterr().out
    assert "pkg-1.0-cp313-linux.whl" in out.split("Error:")[1]


def test_main_rejects_empty_dist_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    build_dir = write_pyproject(
        tmp_path / "pkg", "[tool.hatch.build.hooks.reflex-pyi]\ndependencies = []"
    )
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    assert run_main(monkeypatch, build_dir, dist_dir) == 1


def test_main_ignores_non_distribution_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Only wheels and sdists are artifacts; uv build drops a .gitignore into dist/."""
    build_dir = write_pyproject(
        tmp_path / "pkg", "[tool.hatch.build.hooks.reflex-pyi]\ndependencies = []"
    )
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / ".gitignore").write_text("*\n")
    make_wheel(dist_dir / "pkg-1.0-py3-none-any.whl", ["pkg/a.pyi"])
    assert run_main(monkeypatch, build_dir, dist_dir) == 0


@pytest.mark.parametrize(
    "package_dir",
    [REPO_ROOT, *sorted((REPO_ROOT / "packages").glob("reflex-components-*"))],
    ids=lambda path: path.name or "reflex",
)
def test_stub_generating_packages_are_detected(package_dir: Path):
    """The real reflex and component packages must all be recognised as stub shippers."""
    assert verify_pyi.generates_stubs(verify_pyi.build_table(package_dir))


@pytest.mark.parametrize("package", ["reflex-base", "reflex-release", "reflex-docgen"])
def test_packages_without_stubs_are_not_detected(package: str):
    assert not verify_pyi.generates_stubs(
        verify_pyi.build_table(REPO_ROOT / "packages" / package)
    )
