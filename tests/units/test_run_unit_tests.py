"""Exercise package coverage against a real pytest subprocess."""

from pathlib import Path

import pytest

from scripts import run_unit_tests


@pytest.mark.parametrize(("floor", "expected"), [(100, 2), (40, 0)])
def test_package_coverage_counts_untested_modules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, floor: int, expected: int
):
    """A green test still fails when its package's coverage is too low."""
    package = tmp_path / "packages" / "example"
    source = package / "src" / "example"
    source.mkdir(parents=True)
    (source / "__init__.py").write_text("")
    (source / "covered.py").write_text("VALUE = 1\n")
    (source / "untested.py").write_text("VALUE = 2\n")
    units = package / "tests" / "units"
    units.mkdir(parents=True)
    (units / "test_covered.py").write_text(
        "from example.covered import VALUE\n\ndef test_value():\n    assert VALUE == 1\n"
    )
    (package / "pyproject.toml").write_text(
        f"[tool.reflex-unit-tests]\ncoverage = {floor}\n"
    )
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\npythonpath = ["packages/example/src"]\n'
        '[tool.coverage.run]\nbranch = true\nsource = ["packages/example/src"]\n'
    )
    monkeypatch.setattr(run_unit_tests, "ROOT", tmp_path)
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    monkeypatch.delenv("COVERAGE_PROCESS_START", raising=False)
    result = run_unit_tests.run_suite(
        "example", "packages/example/tests/units", ["-p", "pytest_cov", "-q"]
    )
    assert result == expected
    assert (tmp_path / ".coverage.example").exists()


def test_all_runs_suites_independently(monkeypatch: pytest.MonkeyPatch):
    """All-suite runs enforce each floor and keep running after a failure."""
    monkeypatch.setattr(
        run_unit_tests, "suite_paths", lambda root: {"one": "a", "two": "b"}
    )
    calls = []

    def run(name, path, args):
        calls.append((name, path))
        return 1 if name == "one" else 0

    monkeypatch.setattr(run_unit_tests, "run_suite", run)
    monkeypatch.setattr("sys.argv", ["run_unit_tests", "all"])
    with pytest.raises(SystemExit, match="1"):
        run_unit_tests.main()
    assert calls == [("one", "a"), ("two", "b")]


def test_every_suite_has_a_coverage_floor_and_measured_source():
    """New suites must declare a floor and participate in workspace measurement."""
    config = run_unit_tests.tomllib.loads(
        (run_unit_tests.ROOT / "pyproject.toml").read_text()
    )
    sources = set(config["tool"]["coverage"]["run"]["source"])
    for name, path in run_unit_tests.suite_paths(run_unit_tests.ROOT).items():
        package = (
            run_unit_tests.ROOT
            if name == "reflex"
            else (run_unit_tests.ROOT / path).parents[1]
        )
        manifest = run_unit_tests.tomllib.loads(
            (package / "pyproject.toml").read_text()
        )
        assert 0 < manifest["tool"]["reflex-unit-tests"]["coverage"] <= 100, name
        modules = (
            {"reflex"}
            if name == "reflex"
            else {p.name for p in (package / "src").iterdir() if p.is_dir()}
        )
        assert modules <= sources, (name, modules - sources)
