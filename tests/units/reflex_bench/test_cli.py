"""Tests for reflex_bench.cli."""

from __future__ import annotations

import dataclasses
import json
import os
import platform
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner, Result
from reflex_bench import cli, registry, subjects
from reflex_bench.collectors import cgroup
from reflex_bench.context import Context, Subject
from reflex_bench.registry import Benchmark, Metric
from reflex_bench.schema import dump, load, validate
from reflex_bench.suites.selftest import noise_value

from .factories import WALL, make_doc, make_entry

HARNESS_PYTHON = f"{sys.version_info.major}.{sys.version_info.minor}"
QUICK_SELF_TESTS = (
    "selftest.exact",
    "selftest.fail",
    "selftest.noise",
    "selftest.sleep",
    "selftest.timeout",
)


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("REFLEX_BENCH_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("REFLEX_BENCH_PROFILE", "test-profile")
    for name in ("CI", "GITHUB_ACTIONS", "GITHUB_RUN_ID"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path / "home"


def invoke(*args: str) -> Result:
    return CliRunner().invoke(cli.cli, list(args))


def _noise_run(path: str, *args: str) -> Result:
    return invoke(
        "run",
        "selftest.noise",
        "--param",
        "cv=5",
        "--runs",
        "30",
        "--no-save",
        "--json",
        path,
        *args,
    )


def test_list_self_tests(home: Path):
    result = invoke("list", "--suite", "selftest")
    assert result.exit_code == 0, result.output
    assert result.output.splitlines()[0].split() == [
        "id",
        "kind",
        "metrics",
        "suites",
        "estimate",
    ]
    assert "bytes (B, exact)" in result.output
    assert result.output.splitlines()[-1].startswith("10 benchmarks")


def test_list_estimates_the_timeout_self_test_as_one_sample(home: Path):
    result = invoke("list", "selftest.timeout", "--suite", "selftest")
    assert result.exit_code == 0, result.output
    assert result.output.splitlines()[1].endswith("~0.5 s")


def test_min_runs_alone_raises_the_default_max_runs(home: Path):
    result = invoke(
        "run", "selftest.exact", "--min-runs", "40", "--no-save", "--json", "e.json"
    )
    assert result.exit_code == 0, result.output
    policy = load(Path("e.json"))["policy"]
    assert (policy["min_runs"], policy["max_runs"]) == (40, 40)


@pytest.mark.parametrize(
    "benchmark_id",
    [
        "browser.dev.ready",
        "events.simple.capacity[manager=memory,sessions=10]",
        "hmr.render.leaf[app=playground]",
        "lifecycle.compile.warm[app=playground]",
        "size.export[app=playground]",
    ],
)
def test_list_shows_each_suite_and_hides_self_tests(home: Path, benchmark_id: str):
    result = invoke("list")
    assert result.exit_code == 0, result.output
    names = [line.split()[0] for line in result.output.splitlines()[1:-1]]
    assert benchmark_id in names
    assert not any(name.startswith("selftest.") for name in names)
    assert result.output.splitlines()[-1].startswith(f"{len(names)} benchmarks")


def test_list_says_when_nothing_is_selected(home: Path):
    empty = invoke("list", "nothing.*")
    assert empty.exit_code == 0
    assert (
        "no benchmarks selected (self-tests are listed with --suite selftest)"
        in empty.output
    )


def test_run_writes_json(home: Path):
    result = invoke(
        "run",
        "selftest.sleep",
        "--param",
        "ms=10",
        "--runs",
        "3",
        "--no-save",
        "--json",
        "out.json",
    )
    assert result.exit_code == 0, result.output
    doc = load(Path("out.json"))
    (entry,) = doc["benchmarks"]
    assert entry["id"] == "selftest.sleep"
    assert entry["params"] == {"ms": 10}
    assert entry["status"] == "ok"
    assert entry["metrics"]["wall"]["summary"]["A"]["n"] == 3
    assert entry["metrics"]["wall"]["summary"]["A"]["median"] >= 0.009
    assert doc["invocation"]["argv"] == [
        "run",
        "selftest.sleep",
        "--param",
        "ms=10",
        "--runs",
        "3",
        "--no-save",
        "--json",
        "out.json",
    ]
    assert doc["invocation"]["mode"] == doc["invocation"]["kind"] == "local"
    assert doc["policy"]["runs"] == 3
    assert doc["machine"]["profile_id"] == "test-profile"
    assert not home.joinpath("results").exists()
    assert "selftest.sleep[ms=10]" in result.output
    assert "saved out.json" in result.output


def test_run_self_tests_reports_failures_and_exits_zero(home: Path):
    # The selftest.app.* and selftest.events.* benchmarks start real processes;
    # test_selftest_app.py and suites/test_events_app.py run them.
    result = invoke(
        "run", "--suite", "selftest", *QUICK_SELF_TESTS,
        "--runs", "2", "--no-save", "--json", "all.json",
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    statuses = {
        entry["id"]: entry["status"] for entry in load(Path("all.json"))["benchmarks"]
    }
    assert statuses == {
        "selftest.exact": "ok",
        "selftest.fail": "failed",
        "selftest.noise": "ok",
        "selftest.sleep": "ok",
        "selftest.timeout": "timeout",
    }
    assert (
        "\N{BALLOT X} failed: RuntimeError: selftest.fail always fails" in result.output
    )
    assert "\N{BALLOT X} timeout: sample() exceeded the 0.5 s timeout" in result.output


def test_run_autosaves_and_resolves_baselines(home: Path):
    first = invoke("run", "selftest.exact", "--save-as", "main")
    assert first.exit_code == 0, first.output
    saved = sorted((home / "results" / "test-profile").glob("*.json"))
    assert [path.name.split("_")[0] for path in saved] == ["0001"]
    assert (home / "baselines" / "test-profile" / "main.json").is_file()
    for ref in ("main", "0001", str(saved[0])):
        result = invoke("run", "selftest.exact", "--no-save", "--baseline", ref)
        assert result.exit_code == 0, result.output
        assert f"reflex-bench compare {ref} this run" in result.output
        assert "~ below threshold" in result.output


def test_known_regression_fails_with_exit_code_2(home: Path):
    assert _noise_run("base.json", "--seed", "1").exit_code == 0
    result = _noise_run(
        "head.json",
        "--seed",
        "2",
        "--param",
        "shift=1.2",
        "--baseline",
        "base.json",
        "--fail-on",
        "regression",
    )
    assert result.exit_code == 2, result.output
    assert "regressed" in result.output
    head = load(Path("head.json"))
    assert head["benchmarks"][0].get("hidden_params") == {"shift": 1.2}
    comparison = head["benchmarks"][0]["metrics"]["value"]["comparison"]
    assert comparison is not None
    assert comparison["verdict"] == "regressed"
    assert head.get("compared_to", {}).get("base_label") == "base.json"
    # Locally regressions do not fail by default; with CI=true they do.
    assert (
        _noise_run(
            "x.json", "--param", "shift=1.2", "--baseline", "base.json"
        ).exit_code
        == 0
    )


def test_inconclusive_exit_code(home: Path):
    base = invoke(
        "run",
        "selftest.noise",
        "--param",
        "cv=5",
        "--runs",
        "3",
        "--no-save",
        "--json",
        "a.json",
    )
    assert base.exit_code == 0
    result = invoke(
        "run", "selftest.noise", "--param", "cv=5", "--runs", "3", "--no-save",
        "--baseline", "a.json", "--fail-on-inconclusive",
    )  # fmt: skip
    assert result.exit_code == 3, result.output
    assert "? inconclusive (~6 runs/side needed)" in result.output


def test_compare_formats_and_exit_codes(home: Path, monkeypatch: pytest.MonkeyPatch):
    assert _noise_run("base.json", "--seed", "1").exit_code == 0
    assert _noise_run("head.json", "--seed", "2", "--param", "shift=1.2").exit_code == 0

    term = invoke("compare", "base.json", "head.json")
    assert term.exit_code == 0, term.output
    assert term.output.startswith("reflex-bench compare base.json head.json")
    assert "1 regressed" in term.output

    md = invoke("compare", "base.json", "head.json", "--format", "md")
    assert md.exit_code == 0
    assert "| Benchmark | Metric | Base | Head | Change | Test | Verdict |" in md.output
    assert "**regressed**" in md.output

    annotated = json.loads(
        invoke("compare", "base.json", "head.json", "--format", "json").output
    )
    assert validate(annotated) == []
    assert annotated["compared_to"]["base_label"] == "base.json"

    assert (
        invoke("compare", "base.json", "head.json", "--threshold", "50").exit_code == 0
    )
    assert (
        invoke("compare", "base.json", "head.json", "--fail-on", "regression").exit_code
        == 2
    )
    monkeypatch.setenv("CI", "true")
    assert invoke("compare", "base.json", "head.json").exit_code == 2


def _failing_head_files() -> None:
    exact = Metric(unit="B", direction="lower", assume="exact")
    base = make_doc(
        [
            make_entry("selftest.exact", {"bytes": (exact, [238_400])}),
            make_entry("selftest.fail", {"wall": (WALL, [1.0] * 6)}),
        ],
        invocation_id="base",
    )
    head = make_doc(
        [
            make_entry("selftest.exact", {"bytes": (exact, [238_400])}),
            make_entry(
                "selftest.fail", {"wall": (WALL, [])}, status="failed", error="boom"
            ),
        ],
        invocation_id="head",
    )
    dump(base, Path("base.json"))
    dump(head, Path("head.json"))


def test_compare_fails_when_a_benchmark_starts_failing(
    home: Path, monkeypatch: pytest.MonkeyPatch
):
    _failing_head_files()
    term = invoke("compare", "base.json", "head.json")
    assert term.exit_code == 0, term.output
    assert "selftest.fail: regressed (ok in base, failed in head): boom" in term.output
    assert "1 failed in head" in term.output
    md = invoke("compare", "base.json", "head.json", "--format", "md")
    assert "- `selftest.fail`: **regressed** (ok in base, failed in head): boom" in (
        md.output
    )
    assert (
        invoke("compare", "base.json", "head.json", "--fail-on", "regression").exit_code
        == 2
    )
    monkeypatch.setenv("CI", "true")
    assert invoke("compare", "base.json", "head.json").exit_code == 2


def test_run_fails_when_a_benchmark_starts_failing(home: Path):
    _failing_head_files()
    result = invoke(
        "run", "selftest.fail", "selftest.exact", "--no-save",
        "--baseline", "base.json", "--fail-on", "regression",
    )  # fmt: skip
    assert result.exit_code == 2, result.output
    assert "selftest.fail: regressed (ok in base, failed in head)" in result.output


def test_compare_refuses_other_profiles_unless_forced(
    home: Path, monkeypatch: pytest.MonkeyPatch
):
    assert _noise_run("base.json", "--seed", "1").exit_code == 0
    monkeypatch.setenv("REFLEX_BENCH_PROFILE", "other-profile")
    assert _noise_run("head.json", "--seed", "2").exit_code == 0
    refused = invoke("compare", "base.json", "head.json")
    assert refused.exit_code == 1
    assert "machine profile differs: test-profile vs other-profile" in refused.output
    assert "nothing compared: no benchmark has samples on both sides" in refused.output
    forced = invoke("compare", "base.json", "head.json", "--force")
    assert forced.exit_code == 0, forced.output
    assert "(forced: series keys not checked)" in forced.output


def test_ci_mode(home: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_RUN_ID", "42")
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_REPOSITORY", "reflex-dev/reflex")
    monkeypatch.setenv("RUNNER_NAME", "runner-1")
    result = invoke(
        "run", "selftest.exact", "--no-save", "--json", "ci.json", "--kind", "pr"
    )
    assert result.exit_code == 0, result.output
    invocation = load(Path("ci.json"))["invocation"]
    assert invocation["mode"] == "ci"
    assert load(Path("ci.json"))["policy"]["fail_on"] == "regression"
    assert invocation["kind"] == "pr"
    assert invocation["ci"] == {
        "provider": "github",
        "run_id": "42",
        "url": "https://github.com/reflex-dev/reflex/actions/runs/42",
        "runner": "runner-1",
    }
    assert "[1/1] selftest.exact ok \N{MIDDLE DOT} 1 sample" in result.output


def test_ndjson_goes_to_stdout_and_humans_to_stderr(home: Path):
    result = invoke("run", "selftest.exact", "--no-save", "--ndjson")
    assert result.exit_code == 0
    events = [json.loads(line) for line in result.stdout.splitlines()]
    assert [event["event"] for event in events] == [
        "benchmark_start",
        "sample",
        "benchmark_end",
        "run_end",
    ]
    assert events[1]["values"] == {"bytes": 238_400.0}
    assert events[-1]["exit_code"] == 0
    assert events[-1]["statuses"] == {"ok": 1}
    assert "238.4 kB (exact)" in result.stderr


def test_all_benchmarks_failing_is_a_harness_error(home: Path):
    result = invoke("run", "selftest.fail", "--no-save")
    assert result.exit_code == 1


def test_smoke_run(home: Path):
    result = invoke(
        "run",
        "selftest.sleep",
        "--param",
        "ms=10",
        "--smoke",
        "--no-save",
        "--json",
        "s.json",
    )
    assert result.exit_code == 0, result.output
    (entry,) = load(Path("s.json"))["benchmarks"]
    assert len(entry["sample_meta"]) == 1
    assert entry["metrics"]["wall"]["summary"] == {}
    assert "(smoke)" in result.output


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("run", "nothing.matches"), "no benchmark matches nothing.matches"),
        (("run", "selftest.exact", "--param", "bogus=1"), "unknown --param bogus"),
        (("run", "selftest.exact", "--param", "novalue"), "--param expects KEY=VALUE"),
        (
            ("run", "selftest.exact", "--min-runs", "5", "--max-runs", "2"),
            "max-runs must be >= min-runs",
        ),
        (("run", "selftest.exact", "--baseline", "missing"), "no baseline 'missing'"),
        (("run", "--suite", "weekly"), "Invalid value for '--suite'"),
        (("run", "selftest.exact", "--save-as", "../x"), "may only use letters"),
    ],
)
def test_usage_errors_exit_with_1(home: Path, args: tuple[str, ...], message: str):
    result = invoke(*args)
    assert result.exit_code == 1
    assert message in result.output


def test_invalid_result_files_are_rejected(home: Path):
    Path("bad.json").write_text("{}", encoding="utf-8")
    result = invoke("show", "bad.json")
    assert result.exit_code == 1
    assert "is not a valid reflex-bench/1 document" in result.output


def test_show(home: Path):
    assert _noise_run("base.json", "--seed", "1").exit_code == 0
    result = invoke("show", "base.json", "--samples")
    assert result.exit_code == 0, result.output
    assert result.output.startswith("reflex-bench ")
    assert "selftest.noise[cv=5] \N{MIDDLE DOT} value [A]" in result.output
    assert (
        _noise_run("head.json", "--seed", "2", "--baseline", "base.json").exit_code == 0
    )
    assert (
        "reflex-bench compare base.json this run" in invoke("show", "head.json").output
    )


def test_export(home: Path):
    assert _noise_run("base.json", "--seed", "1").exit_code == 0
    bmf = invoke("export", "base.json", "--to", "bmf")
    assert bmf.exit_code == 0
    assert set(json.loads(bmf.output)["selftest.noise[cv=5]"]["value"]) == {
        "value",
        "lower_value",
        "upper_value",
    }
    assert invoke("export", "base.json", "--to", "md", "-o", "out.md").exit_code == 0
    assert (
        Path("out.md")
        .read_text(encoding="utf-8")
        .startswith("### reflex-bench: reflex ")
    )


def test_doctor(home: Path):
    result = invoke("doctor")
    assert result.exit_code == 0
    assert "governor" in result.output
    assert "profile: test-profile" in result.output


@pytest.mark.parametrize(
    ("probed", "line"),
    [
        (("user", None), "\N{CHECK MARK} cgroup scope  ok (user systemd)"),
        (("sudo", None), "\N{CHECK MARK} cgroup scope  ok (sudo)"),
        (
            (None, "systemd-run not found"),
            (
                "\N{MIDDLE DOT} cgroup scope  unavailable: systemd-run not found:"
                " peak memory falls back to PSS sampling"
            ),
        ),
    ],
)
def test_doctor_reports_cgroup_scopes(
    home: Path,
    monkeypatch: pytest.MonkeyPatch,
    probed: tuple[str | None, str | None],
    line: str,
):
    monkeypatch.setattr(cgroup, "probe", lambda: probed)
    result = invoke("doctor")
    assert result.exit_code == 0
    assert line in result.output.splitlines()


def test_version_and_help(home: Path):
    assert invoke("--version").exit_code == 0
    help_result = invoke("run", "--help")
    assert help_result.exit_code == 0
    assert "--fail-on-inconclusive" in help_result.output


def test_budgets_check_is_registered(home: Path):
    assert "budgets" in invoke("--help").output
    result = invoke("budgets", "check", "--help")
    assert result.exit_code == 0, result.output
    assert "RESULT" in result.output
    assert "--budgets" in result.output


def test_main_entry_point(home: Path, capsys: pytest.CaptureFixture[str]):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["list", "--suite", "selftest"])
    assert excinfo.value.code == 0
    assert "selftest.exact" in capsys.readouterr().out


def _subject(spec: str) -> Subject:
    return Subject(
        spec=spec,
        source="pypi",
        python=Path(sys.executable),
        reflex_version=spec,
        commit=None,
        dirty=None,
        python_version=platform.python_version(),
    )


@pytest.fixture
def resolved(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Resolve every spec to a subject named after it, without building anything.

    Returns:
        The ``(spec, python)`` of every resolve call.
    """
    calls: list[tuple[str, str]] = []

    def resolve(
        spec: str, *, python: str, home: Path, echo: Callable[[str], None]
    ) -> Subject:
        calls.append((spec, python))
        echo(f"resolved {spec}")
        return _subject(spec)

    monkeypatch.setattr(subjects, "resolve", resolve)
    return calls


@pytest.fixture
def shifted() -> Iterator[None]:
    """Register a benchmark whose values are 20 % higher for the subject 2.0.

    Yields:
        Nothing; the benchmark is unregistered afterwards.
    """

    class Shifted:
        """Log-normal values around 1 s, 1.2 s for the subject 2.0."""

        def sample(self, ctx: Context) -> dict[str, float]:
            shift = 1.2 if ctx.subject.spec == "2.0" else 1.0
            return {"value": noise_value(ctx.rng, 2, shift)}

    bench = Benchmark.define(
        Shifted, id="test.shifted", metrics={"value": Metric("s", "lower")}
    )
    registry.register(bench)
    try:
        yield
    finally:
        registry.REGISTRY.pop(bench.id)


def test_run_measures_the_requested_subject(home: Path, resolved: list):
    result = invoke(
        "run", "selftest.exact", "--reflex", "0.8.23", "--python", "3.11",
        "--no-save", "--json", "r.json",
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    assert resolved == [("0.8.23", "3.11")]
    assert result.output.startswith("resolved 0.8.23\n")
    subject = load(Path("r.json"))["subjects"]["A"]
    assert (subject["spec"], subject["reflex_version"]) == ("0.8.23", "0.8.23")


def test_run_measures_the_workspace_by_default(home: Path, resolved: list):
    assert invoke("run", "selftest.exact", "--no-save").exit_code == 0
    assert resolved == [("workspace", HARNESS_PYTHON)]


@pytest.mark.parametrize(
    "args",
    [
        ("run", "selftest.exact", "--reflex", "latest"),
        ("ab", "selftest.exact", "--base", "latest", "--head", "workspace"),
    ],
)
def test_invalid_subject_specs_are_usage_errors(home: Path, args: tuple[str, ...]):
    result = invoke(*args)
    assert result.exit_code == 1
    assert "expected workspace, a version such as 0.8.23" in result.output


def test_subject_errors_exit_with_1(home: Path, monkeypatch: pytest.MonkeyPatch):
    def resolve(spec: str, **kwargs: Any) -> Subject:
        msg = "uv pip install failed: no reflex 9.9.9"
        raise subjects.SubjectError(msg)

    monkeypatch.setattr(subjects, "resolve", resolve)
    result = invoke("run", "selftest.exact", "--reflex", "9.9.9", "--no-save")
    assert result.exit_code == 1
    assert "uv pip install failed: no reflex 9.9.9" in result.output


def test_ab_finds_a_shift_between_subjects(home: Path, resolved: list, shifted: None):
    result = invoke(
        "ab", "test.shifted", "--base", "1.0", "--head", "2.0", "--rounds", "12",
        "--seed", "3", "--no-save", "--json", "ab.json", "--fail-on", "regression",
    )  # fmt: skip
    assert result.exit_code == 2, result.output
    assert resolved == [("1.0", HARNESS_PYTHON), ("2.0", HARNESS_PYTHON)]
    doc = load(Path("ab.json"))
    assert doc["invocation"]["kind"] == "local"
    assert doc["policy"]["runs"] == 12
    assert (doc["subjects"]["A"]["spec"], doc["subjects"]["B"]["spec"]) == (
        "1.0",
        "2.0",
    )
    (entry,) = doc["benchmarks"]
    assert [meta["arm"] for meta in entry["sample_meta"][:4]] == ["A", "B", "B", "A"]
    comparison = entry["metrics"]["value"]["comparison"]
    assert comparison is not None
    assert comparison["verdict"] == "regressed"
    assert (comparison["base"]["arm"], comparison["head"]["arm"]) == ("A", "B")
    assert (comparison["base"]["n"], comparison["head"]["n"]) == (12, 12)
    assert "B: reflex 2.0 (2.0)" in result.output
    assert "value [A]" in result.output
    assert "value [B]" in result.output
    assert "reflex-bench compare A=1.0 B=2.0" in result.output
    assert "1 regressed" in result.output
    assert "runs Python" not in result.output


def test_ab_a_a_control(home: Path, resolved: list, shifted: None):
    result = invoke(
        "ab", "test.shifted", "--head", "2.0", "--aa", "--rounds", "12",
        "--seed", "3", "--json", "aa.json", "--fail-on", "regression",
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    assert resolved == [("2.0", HARNESS_PYTHON)]
    doc = load(Path("aa.json"))
    assert doc["invocation"]["kind"] == "aa"
    assert doc["subjects"]["A"] == doc["subjects"]["B"]
    comparison = doc["benchmarks"][0]["metrics"]["value"]["comparison"]
    assert comparison is not None
    assert comparison["verdict"] in {"unchanged", "inconclusive"}
    # Saved like any other run.
    assert len(list((home / "results" / "test-profile").glob("*.json"))) == 1


def test_ab_random_order_is_reproducible(home: Path, resolved: list, shifted: None):
    def orders(seed: str) -> list[str]:
        result = invoke(
            "ab", "test.shifted", "--base", "1.0", "--head", "2.0", "--rounds", "8",
            "--order", "random", "--seed", seed, "--no-save", "--json", "r.json",
        )  # fmt: skip
        assert result.exit_code == 0, result.output
        entry = load(Path("r.json"))["benchmarks"][0]
        return [meta["arm"] for meta in entry["sample_meta"]]

    assert orders("1") == orders("1")
    assert orders("1") != orders("2")


def test_ab_self_tests_against_the_workspace(home: Path):
    # The selftest.app.* and selftest.events.* benchmarks start real processes.
    result = invoke(
        "ab", "--suite", "selftest", *QUICK_SELF_TESTS,
        "--base", "workspace", "--head", "workspace",
        "--rounds", "6", "--no-save", "--json", "ab.json",
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    doc = load(Path("ab.json"))
    statuses = {entry["id"]: entry["status"] for entry in doc["benchmarks"]}
    assert statuses == {
        "selftest.exact": "ok",
        "selftest.fail": "failed",
        "selftest.noise": "ok",
        "selftest.sleep": "ok",
        "selftest.timeout": "timeout",
    }
    noise = next(e for e in doc["benchmarks"] if e["params"] == {"cv": 5})
    assert {arm: s["n"] for arm, s in noise["metrics"]["value"]["summary"].items()} == {
        "A": 6,
        "B": 6,
    }
    assert "not compared: selftest.fail: base status is failed" in result.output


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("--head", "2.0"), "--base is required unless --aa is given"),
        (("--base", "1.0", "--head", "2.0", "--aa"), "--aa takes --head only"),
        (("--base", "1.0"), "Missing option '--head'"),
        (("--base", "1.0", "--head", "2.0", "--order", "abab"), "'--order'"),
        (("--base", "1.0", "--head", "2.0", "--rounds", "0"), "'--rounds'"),
    ],
)
def test_ab_usage_errors(
    home: Path, resolved: list, args: tuple[str, ...], message: str
):
    result = invoke("ab", "selftest.exact", *args)
    assert result.exit_code == 1
    assert message in result.output
    assert resolved == []


def _cached_venv(home: Path, key: str, spec: str, age_days: float) -> Path:
    venv = home / "venvs" / key
    venv.mkdir(parents=True)
    manifest = venv / subjects.MANIFEST
    manifest.write_text(
        json.dumps({
            "spec": spec,
            "source": "pypi",
            "python": "3.12",
            "snapshot": None,
        }),
        encoding="utf-8",
    )
    used = time.time() - age_days * 86_400
    os.utime(manifest, (used, used))
    return venv


def test_subjects_list_and_prune(home: Path):
    assert "no cached subject venvs" in invoke("subjects", "list").output
    old = _cached_venv(home, "a" * 16, "0.8.23", 40)
    _cached_venv(home, "b" * 16, "git:main", 1)
    listed = invoke("subjects", "list")
    assert listed.exit_code == 0, listed.output
    lines = listed.output.splitlines()
    assert lines[0].split() == ["spec", "python", "key", "size", "last", "used"]
    assert lines[1].split()[:3] == ["git:main", "3.12", "b" * 16]
    assert lines[2].split()[:3] == ["0.8.23", "3.12", "a" * 16]
    assert lines[-1].startswith("2 venvs")

    pruned = invoke("subjects", "prune", "--older-than", "30d")
    assert pruned.exit_code == 0, pruned.output
    assert f"removed {old}" in pruned.output
    assert not old.exists()
    assert "nothing to prune" in invoke("subjects", "prune").output


@pytest.mark.parametrize("age", ["30", "30 days", "-1d", "d"])
def test_prune_rejects_invalid_ages(home: Path, age: str):
    result = invoke("subjects", "prune", "--older-than", age)
    assert result.exit_code == 1
    assert "Invalid value for '--older-than'" in result.output


def test_ab_warns_when_the_arms_run_different_pythons(
    home: Path, monkeypatch: pytest.MonkeyPatch, shifted: None
):
    def resolve(spec: str, **kwargs: Any) -> Subject:
        python = "3.12.3" if spec == "1.0" else "3.14.7"
        return dataclasses.replace(_subject(spec), python_version=python)

    monkeypatch.setattr(subjects, "resolve", resolve)
    result = invoke(
        "ab", "test.shifted", "--base", "1.0", "--head", "2.0", "--rounds", "2",
        "--no-save",
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    assert "arm A runs Python 3.12 and arm B Python 3.14" in result.output
