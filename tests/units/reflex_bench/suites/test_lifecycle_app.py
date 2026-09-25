"""Run the lifecycle benchmarks and the generated apps for real.

They compile and run real apps (bun, node and network needed), so they only run
when asked: ``REFLEX_BENCH_APP_TESTS=1 uv run pytest
tests/units/reflex_bench/suites/test_lifecycle_app.py``. With
``REFLEX_BENCH_NETWORK_TESTS=1`` as well, they also run against reflex 0.8.23
from PyPI, on Python 3.12.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from reflex_bench import subjects
from reflex_bench.context import Subject, subject_env, workspace_subject
from reflex_bench.drivers.app_process import cache_env, run_cli
from reflex_bench.fixtures.generate import GenParams, generate
from reflex_bench.schema import entry_name, load

from .test_selftest_app import _owned_processes

pytestmark = pytest.mark.skipif(
    os.environ.get("REFLEX_BENCH_APP_TESTS") != "1",
    reason="compiles and runs real reflex apps; set REFLEX_BENCH_APP_TESTS=1",
)
SPECS = [
    "workspace",
    pytest.param(
        "0.8.23",
        marks=pytest.mark.skipif(
            os.environ.get("REFLEX_BENCH_NETWORK_TESTS") != "1",
            reason="installs reflex 0.8.23 from PyPI; set REFLEX_BENCH_NETWORK_TESTS=1",
        ),
    ),
]


@pytest.fixture(scope="module")
def home(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Share one bench home (venvs, caches) between the tests of the module.

    Returns:
        The bench home.
    """
    return tmp_path_factory.mktemp("home")


def _subject(spec: str, home: Path) -> Subject:
    """Build or reuse the environment of a subject.

    Returns:
        The subject.
    """
    if spec == "workspace":
        return workspace_subject()
    return subjects.resolve(spec, python="3.12", home=home)


@pytest.mark.parametrize("spec", SPECS)
@pytest.mark.parametrize("pages", [1, 10])
def test_the_generated_app_compiles(tmp_path: Path, home: Path, spec: str, pages: int):
    subject = _subject(spec, home)
    app = tmp_path / "app"
    generate(app, GenParams(pages=pages))
    env = {
        **subject_env(subject.python),
        **cache_env(reflex_dir=home / "reflex" / spec),
    }
    run_cli(subject.python, ["compile"], cwd=app, env=env, timeout=600).check()
    routes = sorted(path.name for path in (app / ".web" / "app" / "routes").iterdir())
    assert routes == sorted([
        "[404]._index.jsx",
        "_index.jsx",
        *(f"[page-{page}]._index.jsx" for page in range(1, pages)),
    ])


@pytest.mark.parametrize("spec", SPECS)
@pytest.mark.parametrize(
    "selection",
    [
        ["--suite", "daily", "lifecycle.*"],
        ["lifecycle.scale.*", "--param", "pages=10"],
    ],
    ids=["daily", "scale"],
)
def test_smoke_runs(tmp_path: Path, home: Path, spec: str, selection: list[str]):
    out = tmp_path / "result.json"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "reflex_bench",
            "run",
            "--smoke",
            "--reflex",
            spec,
            "--python",
            "3.12",
            *selection,
            "--no-save",
            "--json",
            str(out),
        ],
        env={**os.environ, "REFLEX_BENCH_HOME": str(home)},
        capture_output=True,
        text=True,
        timeout=3600,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    statuses = {entry_name(entry): entry["status"] for entry in load(out)["benchmarks"]}
    unsupported = (
        {"lifecycle.run.preview.ready[app=playground]"} if spec == "0.8.23" else set()
    )
    assert statuses == {
        name: "unsupported" if name in unsupported else "ok" for name in statuses
    }
    assert len(statuses) == (12 if selection[0] == "--suite" else 2)
    assert _owned_processes() == []
