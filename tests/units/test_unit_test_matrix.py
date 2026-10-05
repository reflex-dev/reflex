"""Tests for selective unit-test CI."""

import io
import json
from pathlib import Path

import pytest
import yaml

from scripts import unit_test_matrix as selection
from scripts.changed_paths import changed_files


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Create a workspace with a dependency chain and an unrelated package.

    Args:
        tmp_path: Temporary directory.

    Returns:
        Workspace root.
    """
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "reflex"\n')
    for name, dependencies in {
        "base": [],
        "widget": ["base>=1"],
        "consumer": ["widget[extra]>=1"],
        "other": [],
    }.items():
        package = tmp_path / "packages" / name
        (package / "tests").mkdir(parents=True)
        (package / "pyproject.toml").write_text(
            f'[project]\nname = "{name}"\ndependencies = {json.dumps(dependencies)}\n'
        )
    return tmp_path


@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        (["packages/widget/src/widget.py"], ["consumer", "reflex", "widget"]),
        (["packages/widget/tests/test_widget.py"], ["widget"]),
        (["packages/widget/README.md"], ["consumer", "reflex", "widget"]),
        (["packages/base/src/base.py"], ["base", "consumer", "reflex", "widget"]),
        (["tests/units/test_app.py"], ["reflex"]),
        (["docs/guide.md", "README.md"], []),
        (["tests/integration/test_app.py"], ["reflex"]),
        (["tests/benchmarks/support/apps.py"], ["reflex"]),
        (["tests/performance/conftest.py"], ["reflex"]),
        ([".github/rulesets/main-required-checks.json"], ["reflex"]),
        ([".github/workflows/integration_tests.yml"], ["reflex"]),
        (
            ["packages/other/tests/test_old.py", "packages/widget/tests/test_new.py"],
            ["other", "widget"],
        ),
    ],
)
def test_select_suites(workspace: Path, paths: list[str], expected: list[str]):
    """Owners and runtime dependents run without unrelated suites."""
    assert selection.select_suites(paths, workspace) == expected


@pytest.mark.parametrize(
    "paths",
    [
        [],
        ["uv.lock"],
        ["pyproject.toml"],
        ["tests/unit_fixtures.py"],
        ["tests/units/conftest.py"],
        ["tests/units/mock_redis.py"],
        ["tests/units/states/upload.py"],
        ["scripts/unit_test_matrix.py"],
        [".github/workflows/unit_tests.yml"],
        ["reflex/app.py"],
        ["packages/deleted/src/code.py"],
    ],
)
def test_shared_changes_run_every_suite(workspace: Path, paths: list[str]):
    """Shared infrastructure and unknown removed packages cannot skip tests."""
    assert selection.select_suites(paths, workspace) == sorted(
        selection.suite_paths(workspace)
    )


def test_rename_selects_both_owners(workspace: Path):
    """Moving a test between packages reruns both owners."""
    paths = changed_files([
        json.dumps({
            "filename": "packages/widget/tests/test_new.py",
            "previous_filename": "packages/other/tests/test_old.py",
        })
    ])
    assert selection.select_suites(paths, workspace) == ["other", "widget"]


def test_dependency_cycles_terminate(workspace: Path):
    """Cycles and optional dependencies still select every consumer."""
    with (workspace / "packages/base/pyproject.toml").open("a") as output:
        output.write('[project.optional-dependencies]\nextra = ["consumer"]\n')
    assert selection.select_suites(["packages/widget/src/code.py"], workspace) == [
        "base",
        "consumer",
        "reflex",
        "widget",
    ]


def test_repository_suites():
    """Every package with tests is discoverable and a leaf test stays local."""
    suites = selection.suite_paths(selection.ROOT)
    assert suites["reflex-base"] == "packages/reflex-base/tests"
    assert selection.select_suites([
        "packages/reflex-build-sdk/tests/reflex_build_sdk_tests/test_base.py"
    ]) == ["reflex-build-sdk"]
    assert "reflex-components-core" in selection.select_suites([
        "packages/reflex-base/src/reflex_base/vars/base.py"
    ])


def test_matrix_cli(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture):
    """An irrelevant PR emits an empty matrix and skips the matrix job."""
    monkeypatch.setattr("sys.argv", ["unit_test_matrix.py"])
    monkeypatch.setattr("sys.stdin", io.StringIO('{"filename":"README.md"}\n'))
    selection.main()
    assert capsys.readouterr().out == 'matrix={"suite":[]}\nrun=false\n'


def test_main_branch_runs_full_suite():
    """Full-suite runs retain the existing workspace coverage floor."""
    assert selection.matrix([], all_tests=True) == {
        "suite": [{"name": "all", "path": selection.ALL_TESTS, "coverage": "72"}]
    }


def test_workflow_uses_selected_suites():
    """Every PR matrix leg uses the selector and the fixed gate covers it."""
    workflow = yaml.safe_load(
        (selection.ROOT / ".github/workflows/unit_tests.yml").read_text()
    )
    jobs = workflow["jobs"]
    job = jobs["unit-tests"]
    assert "needs.changes.outputs.matrix" in job["strategy"]["matrix"]["suite"]
    assert job["if"] == "needs.changes.outputs.run == 'true'"
    assert "unit-tests" in jobs["unit-tests-gate"]["needs"]
    commands = "\n".join(step.get("run", "") for step in job["steps"])
    assert "pytest $TEST_PATHS" in commands
    assert "--cov-fail-under=$COVERAGE_FLOOR" in commands


def test_shared_changes_use_one_full_suite_matrix():
    """Shared edits avoid hundreds of package legs and enforce full coverage."""
    assert selection.matrix(["uv.lock"]) == selection.matrix([], all_tests=True)


def test_linux_only_bench_suite_is_excluded_on_windows():
    """An empty Windows bench collection must not fail the required gate."""
    workflow = yaml.safe_load(
        (selection.ROOT / ".github/workflows/unit_tests.yml").read_text()
    )
    suite = selection.matrix(["packages/reflex-bench/tests/test_example.py"])["suite"][
        0
    ]
    assert {"os": "windows-latest", "suite": suite} in workflow["jobs"]["unit-tests"][
        "strategy"
    ]["matrix"]["exclude"]
