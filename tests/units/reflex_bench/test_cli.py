"""Tests for reflex_bench.cli."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from reflex_bench import cli
from reflex_bench.schema import load, validate


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
    names = [line.split()[0] for line in result.output.splitlines()[1:-1]]
    assert names == [
        "selftest.exact",
        "selftest.fail",
        "selftest.noise[cv=5]",
        "selftest.noise[cv=20]",
        "selftest.sleep[ms=10]",
        "selftest.sleep[ms=50]",
        "selftest.timeout",
    ]
    assert result.output.splitlines()[0].split() == [
        "id",
        "kind",
        "metrics",
        "suites",
        "estimate",
    ]
    assert "bytes (B, exact)" in result.output
    assert result.output.splitlines()[-1].startswith("7 benchmarks")


def test_list_hides_self_tests_by_default(home: Path):
    result = invoke("list")
    assert result.exit_code == 0
    assert (
        "no benchmarks selected (self-tests are listed with --suite selftest)"
        in result.output
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
    result = invoke(
        "run", "--suite", "selftest", "--runs", "2", "--no-save", "--json", "all.json"
    )
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
    saved = sorted((home / "results" / "test-profile").iterdir())
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


def test_version_and_help(home: Path):
    assert invoke("--version").exit_code == 0
    help_result = invoke("run", "--help")
    assert help_result.exit_code == 0
    assert "--fail-on-inconclusive" in help_result.output


def test_main_entry_point(home: Path, capsys: pytest.CaptureFixture[str]):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["list", "--suite", "selftest"])
    assert excinfo.value.code == 0
    assert "selftest.exact" in capsys.readouterr().out
