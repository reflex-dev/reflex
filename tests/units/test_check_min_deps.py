"""Unit tests for scripts/check_min_deps.py (the minimum-dependency-version checker)."""

import sys
from pathlib import Path

import pytest

# The script relies on ``tomllib`` (stdlib only on 3.11+); on 3.10 it falls back to the
# ``tomli`` backport. Skip the whole module when neither is available, so the tests still
# run on 3.10 whenever ``tomli`` happens to be installed.
if sys.version_info < (3, 11):
    pytest.importorskip(
        "tomli", reason="check_min_deps requires tomli on Python < 3.11"
    )

from scripts import check_min_deps


def test_install_target_without_extras(tmp_path: Path):
    package = check_min_deps.Package(
        name="pkg", project_dir=tmp_path, source_dir=tmp_path, extras=()
    )
    assert package.install_target() == str(tmp_path)


def test_install_target_with_extras(tmp_path: Path):
    package = check_min_deps.Package(
        name="pkg", project_dir=tmp_path, source_dir=tmp_path, extras=("db", "extra")
    )
    assert package.install_target() == f"{tmp_path}[db,extra]"


def test_single_source_dir(tmp_path: Path):
    module = tmp_path / "the_module"
    module.mkdir()
    (tmp_path / "not_a_dir.txt").write_text("")
    assert check_min_deps._single_source_dir(tmp_path) == module


def test_single_source_dir_requires_exactly_one(tmp_path: Path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    with pytest.raises(ValueError, match="exactly one module directory"):
        check_min_deps._single_source_dir(tmp_path)


def test_discover_packages_includes_root_first_and_skips_excluded():
    packages = check_min_deps.discover_packages()
    names = [p.name for p in packages]

    assert names[0] == "reflex", "root reflex package should be checked first"
    assert "reflex-base" in names
    assert not check_min_deps.SKIP_PACKAGES.intersection(names)

    for package in packages:
        assert package.source_dir.is_dir(), f"{package.name} source dir must exist"
        assert (package.project_dir / "pyproject.toml").is_file()


def test_discover_packages_records_optional_extras():
    by_name = {p.name: p for p in check_min_deps.discover_packages()}
    # The root package declares a `db` optional-dependency group.
    assert "db" in by_name["reflex"].extras


def test_pyright_errors_keys_and_filters_severity():
    report = {
        "generalDiagnostics": [
            {
                "file": "/abs/foo.py",
                "severity": "error",
                "message": "boom",
                "range": {"start": {"line": 9, "character": 4}},
            },
            {
                "file": "/abs/foo.py",
                "severity": "warning",
                "message": "ignore me",
                "range": {"start": {"line": 1, "character": 0}},
            },
        ]
    }
    errors = check_min_deps._pyright_errors(report)

    assert list(errors) == [("/abs/foo.py", 9, 4, "boom")]
    # Line/character are converted to 1-based in the display string.
    assert errors["/abs/foo.py", 9, 4, "boom"] == "/abs/foo.py:10:5 - error: boom"


def test_pyright_errors_delta_cancels_shared_noise():
    def report(messages: list[tuple[str, int]]) -> dict:
        return {
            "generalDiagnostics": [
                {
                    "file": "/abs/foo.py",
                    "severity": "error",
                    "message": msg,
                    "range": {"start": {"line": line, "character": 0}},
                }
                for msg, line in messages
            ]
        }

    # A shared, undeclared-import error appears in both resolutions; only the
    # minimum-version-specific error should remain in the delta.
    baseline = check_min_deps._pyright_errors(report([("missing optional import", 1)]))
    minimum = check_min_deps._pyright_errors(
        report([("missing optional import", 1), ("model_dump is unknown", 50)])
    )

    new = minimum.keys() - baseline.keys()
    assert new == {("/abs/foo.py", 50, 0, "model_dump is unknown")}
