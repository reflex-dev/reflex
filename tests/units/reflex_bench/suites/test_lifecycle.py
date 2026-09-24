"""Tests for reflex_bench.suites.lifecycle, with the app driver replaced by recorders."""

from __future__ import annotations

import dataclasses
import json
import os
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from reflex_bench import fixtures
from reflex_bench.collectors.phases import ClassTotals, TreeReport
from reflex_bench.context import Context
from reflex_bench.drivers.app_process import AppStartError, CliResult, Readiness
from reflex_bench.fixtures import generate
from reflex_bench.registry import SampleResult, discover, select
from reflex_bench.scheduler import plan
from reflex_bench.suites import lifecycle

from tests.units.reflex_bench.factories import make_context

PLAYGROUND_HASH = fixtures.describe_playground()["content_hash"]
TIME_EXTRA = {
    "phases",
    "timing",
    "cpu_method",
    "memory_method",
    "peak_reset",
    "returncode",
}


@dataclasses.dataclass
class Call:
    """One recorded run_cli call."""

    args: list[str]
    cwd: Path
    env: dict[str, str]
    kwargs: dict[str, Any]


class FakeCli:
    """Records run_cli calls and returns canned results."""

    def __init__(self) -> None:
        """Start with no calls."""
        self.calls: list[Call] = []

    def __call__(
        self,
        python: Path,
        args: Sequence[str],
        *,
        cwd: Path,
        env: dict[str, str],
        **kwargs: Any,
    ) -> CliResult:
        """Record a call.

        Returns:
            A successful result; with ``phases``, one with an attribution.
        """
        assert python == Path(sys.executable)
        self.calls.append(Call(list(args), cwd, dict(env), kwargs))
        phases = kwargs.get("phases", False)
        empty = ClassTotals(wall_s=0.0, cpu_s=0.0, intervals=[])
        interpreter = ClassTotals(wall_s=2.5, cpu_s=3.0, intervals=[(0.0, 2.5)])
        if kwargs.get("scope") is not None:
            method = "cgroup"
        else:
            method = "pss_sampling" if kwargs.get("sample_memory") else None
        return CliResult(
            args=[*args, *(["--loglevel", "debug"] if phases else [])],
            returncode=0,
            wall_s=2.5,
            lines=[],
            timeout_s=kwargs["timeout"],
            cpu_s=3.25,
            peak_mem_bytes=None if method is None else 300_000_000,
            memory_method=method,
            timing={"compile": 0.5} if phases else {},
            tree=TreeReport(
                classes={"python": interpreter, "install": empty, "frontend": empty}
            )
            if phases
            else None,
        )


class FakeApp:
    """Stands in for AppProcess: records its settings and whether it was stopped."""

    started: list[FakeApp] = []
    fail_start = False

    def __init__(self, python: Path, app_dir: Path, **kwargs: Any) -> None:
        """Record the settings."""
        self.python = python
        self.app_dir = app_dir
        self.kwargs = kwargs
        self.stopped = False
        self.readiness: Readiness | None = None

    def start(self) -> Readiness:
        """Record the start.

        Returns:
            The readiness.

        Raises:
            AppStartError: With ``fail_start``, or once stopped.
        """
        FakeApp.started.append(self)
        if self.stopped:
            msg = "reflex run was stopped before it started"
            raise AppStartError(msg, [])
        if FakeApp.fail_start:
            msg = "reflex run exited with code 1 before it was ready"
            raise AppStartError(msg, ["Error: broken"])
        self.readiness = Readiness(spawned=0.01, ready_line=1.0, process_ready=1.25)
        return self.readiness

    def wait_http_ready(self, path: str | None = None, timeout: float = 120.0) -> float:
        """Answer at once.

        Returns:
            The HTTP-ready time.
        """
        assert self.readiness is not None
        self.readiness.http_ready = 1.5
        return 1.5

    def stop(self, timeout: float = 10.0) -> None:
        """Record the stop."""
        self.stopped = True


class FakeScope:
    """Stands in for CgroupScope on a host with scopes."""

    @staticmethod
    def available() -> str | None:
        """Report scopes as available.

        Returns:
            ``None``.
        """
        return None


@pytest.fixture
def cli(monkeypatch: pytest.MonkeyPatch) -> FakeCli:
    fake = FakeCli()
    monkeypatch.setattr(lifecycle, "run_cli", fake)
    monkeypatch.setattr(lifecycle, "AppProcess", FakeApp)
    # Hosts with and without cgroup scopes record the same calls.
    monkeypatch.setattr(
        lifecycle.CgroupScope, "available", staticmethod(lambda: "none in tests")
    )
    FakeApp.started = []
    FakeApp.fail_start = False
    return fake


@pytest.fixture
def ctx(tmp_path: Path) -> Context:
    work, cache, bins = tmp_path / "work", tmp_path / "cache", tmp_path / "bin"
    shared = tmp_path / "shared"
    for directory in (work, cache, shared, bins):
        directory.mkdir()
    return dataclasses.replace(
        make_context(tmp_path),
        workdir=work,
        cache_dir=cache,
        subject_cache_dir=shared,
        env={"PATH": str(bins), "KEEP": "1"},
    )


def _primed_bun(ctx: Context) -> None:
    """Put a bun into the subject's shared REFLEX_DIR, as a priming init does."""
    bun = ctx.subject_cache_dir / "reflex" / "bun" / "bin" / "bun"
    bun.parent.mkdir(parents=True)
    bun.write_bytes(b"x")


def _instance(bench_id: str, ctx: Context, **params: Any) -> Any:
    """Instantiate a lifecycle benchmark with its first (or only) parameter set.

    Returns:
        The benchmark object; ``ctx.params`` is filled in.
    """
    bench = discover()[bench_id]
    ctx.params = bench.expand(params)[0].merged
    return bench.cls()


def _run(bench: Any, ctx: Context, samples: int = 1) -> list[SampleResult]:
    """Run the hooks of an instance as the scheduler does.

    Returns:
        What each sample returned.
    """
    for hook in ("setup_cache", "setup"):
        if hasattr(bench, hook):
            getattr(bench, hook)(ctx)
    results = []
    for _ in range(samples):
        if hasattr(bench, "prepare"):
            bench.prepare(ctx)
        results.append(bench.sample(ctx))
        if hasattr(bench, "conclude"):
            bench.conclude(ctx)
    return results


def _extra(result: SampleResult) -> dict[str, Any]:
    assert result.extra is not None
    return result.extra


def test_the_suites():
    benchmarks = discover().values()
    lifecycle_ids = {bench.id for bench in select(benchmarks, ["lifecycle.*"])}
    assert {bench.id for bench in select(benchmarks, suite="pr")} == {
        "lifecycle.compile.warm",
        "lifecycle.compile.incremental",
    }
    daily = {bench.id for bench in select(benchmarks, ["lifecycle.*"], "daily")}
    assert daily == lifecycle_ids - {
        "lifecycle.scale.compile.warm",
        "lifecycle.scale.compile.incremental",
    }
    assert {bench.id for bench in select(benchmarks, ["lifecycle.*"], "all")} == (
        lifecycle_ids
    )
    assert discover()["lifecycle.run.preview.ready"].min_version == "0.9.8"


def test_instance_names():
    names = {
        planned.name for planned in plan(select(discover().values(), ["lifecycle.*"]))
    }
    assert "lifecycle.compile.warm[app=playground]" in names
    assert "lifecycle.run.prod.ready[app=playground]" in names
    assert "lifecycle.init.cold" in names
    assert "lifecycle.import" in names
    assert {
        f"lifecycle.scale.compile.warm[pages={pages}]" for pages in (1, 10, 100, 1000)
    } <= names
    scale = discover()["lifecycle.scale.compile.incremental"]
    assert scale.hidden_params == {
        "components_per_page": 20,
        "state_vars": 20,
        "substate_depth": 2,
        "computed_vars": 5,
        "seed": 42,
    }


def _cold_env(ctx: Context, call: Call, name: str, path: Path) -> None:
    assert call.env[name] == str(path)
    assert Path(call.env[name]).is_relative_to(ctx.workdir)


def test_init_cold(cli: FakeCli, ctx: Context):
    bench = _instance("lifecycle.init.cold", ctx)
    (first, second) = _run(bench, ctx, samples=2)
    assert [call.args for call in cli.calls] == [["init", "--template", "blank"]] * 2
    for call in cli.calls:
        assert call.cwd == ctx.workdir / "app"
        _cold_env(ctx, call, "REFLEX_DIR", ctx.workdir / "reflex")
        assert "BUN_INSTALL_CACHE_DIR" not in call.env
        assert call.kwargs["phases"] is True
        assert call.kwargs["sample_memory"] is True
        assert call.kwargs["scope"] is None
    assert ctx.fixture is None
    assert ctx.dims == {"collector": "fallback"}
    assert _extra(first)["deleted_bytes"] == {"web": 0, "reflex_dir": 0}
    assert TIME_EXTRA | {"deleted_bytes"} == _extra(second).keys()


def test_init_cold_prepare_starts_from_nothing(cli: FakeCli, ctx: Context):
    bench = _instance("lifecycle.init.cold", ctx)
    bench.setup(ctx)
    app, reflex_dir = ctx.workdir / "app", ctx.workdir / "reflex"
    (app / ".web").mkdir(parents=True)
    (app / ".web" / "package.json").write_bytes(b"x" * 100)
    (app / "rxconfig.py").write_text("x", encoding="utf-8")
    (reflex_dir / "bun" / "bin").mkdir(parents=True)
    (reflex_dir / "bun" / "bin" / "bun").write_bytes(b"x" * 1000)
    bench.prepare(ctx)
    assert list(app.iterdir()) == []
    assert not reflex_dir.exists()
    result = bench.sample(ctx)
    assert _extra(result)["deleted_bytes"] == {"web": 100, "reflex_dir": 1000}


def test_init_warm(cli: FakeCli, ctx: Context):
    bench = _instance("lifecycle.init.warm", ctx)
    _run(bench, ctx, samples=2)
    prime, *samples = cli.calls
    # setup_cache fills REFLEX_DIR once, in a scratch app, untimed.
    assert prime.args == ["init", "--template", "blank"]
    assert prime.cwd != ctx.workdir / "app"
    assert not prime.cwd.exists()
    assert "phases" not in prime.kwargs
    for call in (prime, *samples):
        assert call.env["REFLEX_DIR"] == str(ctx.subject_cache_dir / "reflex")
    assert [call.args for call in samples] == [["init", "--template", "blank"]] * 2
    assert all(call.cwd == ctx.workdir / "app" for call in samples)
    assert all(call.kwargs["phases"] for call in samples)


def test_a_reflex_dir_holding_a_bun_is_not_primed_again(cli: FakeCli, ctx: Context):
    # One shared REFLEX_DIR per subject: the first instance downloads bun.
    _primed_bun(ctx)
    _run(_instance("lifecycle.init.warm", ctx), ctx)
    _run(_instance("lifecycle.compile.cold", ctx), ctx)
    assert [call.args for call in cli.calls] == [
        ["init", "--template", "blank"],
        ["compile"],
    ]


def test_compile_cold(cli: FakeCli, ctx: Context):
    bench = _instance("lifecycle.compile.cold", ctx)
    results = _run(bench, ctx, samples=2)
    prime, *samples = cli.calls
    assert prime.args == ["init", "--template", "blank"]
    assert prime.env["REFLEX_DIR"] == str(ctx.subject_cache_dir / "reflex")
    for call in samples:
        assert call.args == ["compile"]
        assert call.cwd == ctx.workdir / "app"
        assert call.env["REFLEX_DIR"] == str(ctx.subject_cache_dir / "reflex")
        _cold_env(ctx, call, "BUN_INSTALL_CACHE_DIR", ctx.workdir / "bun-cache")
    assert ctx.fixture == fixtures.describe_playground()
    # Each sample compiles a fresh copy of the playground.
    assert (ctx.workdir / "app" / "rxconfig.py").is_file()
    assert not (ctx.workdir / "app" / fixtures.HASH_FILE).exists()
    assert TIME_EXTRA | {"deleted_bytes"} == _extra(results[0]).keys()


def test_compile_cold_prepare_removes_the_previous_copy_and_bun_cache(
    cli: FakeCli, ctx: Context
):
    bench = _instance("lifecycle.compile.cold", ctx)
    bench.setup(ctx)
    bench.prepare(ctx)
    app, bun_cache = ctx.workdir / "app", ctx.workdir / "bun-cache"
    # What the previous sample's compile left behind.
    (app / ".web" / "node_modules").mkdir(parents=True)
    (app / ".web" / "node_modules" / "react.js").write_bytes(b"x" * 250)
    (app / "reflex.lock").mkdir()
    (bun_cache / "react@19").mkdir(parents=True)
    (bun_cache / "react@19" / "index.js").write_bytes(b"x" * 400)
    bench.prepare(ctx)
    assert not (app / ".web").exists()
    assert not (app / "reflex.lock").exists()
    assert not bun_cache.exists()
    assert (app / "rxconfig.py").is_file()
    result = bench.sample(ctx)
    assert _extra(result)["deleted_bytes"] == {"web": 250, "bun_cache": 400}


def test_compile_warm(cli: FakeCli, ctx: Context):
    bench = _instance("lifecycle.compile.warm", ctx)
    (result,) = _run(bench, ctx)
    prime, sample = cli.calls
    app = ctx.cache_dir / "app"
    # setup_cache copies the playground once and primes it with an untimed compile.
    assert (prime.args, prime.cwd) == (["compile"], app)
    assert "phases" not in prime.kwargs
    assert (sample.args, sample.cwd) == (["compile"], app)
    assert sample.kwargs["phases"] is True
    for call in (prime, sample):
        assert call.env["REFLEX_DIR"] == str(ctx.subject_cache_dir / "reflex")
        assert "BUN_INSTALL_CACHE_DIR" not in call.env
        assert call.env["KEEP"] == "1"
    assert ctx.dims == {"collector": "fallback"}
    assert json.loads((ctx.cache_dir / fixtures.STAMP).read_text()) == ctx.fixture
    assert ctx.fixture == {
        "name": "playground",
        "content_hash": PLAYGROUND_HASH,
        "params": {},
    }
    assert result.values == {"wall": 2.5, "cpu": 3.25, "peak_mem": 300_000_000}
    extra = _extra(result)
    assert extra.keys() == TIME_EXTRA
    assert extra["phases"] == {
        "total": 2.5,
        "cpu_total": 3.25,
        "python": 2.5,
        "install": 0.0,
        "frontend": 0.0,
        "idle": 0.0,
        "cpu": {"python": 3.0, "install": 0.0, "frontend": 0.0},
        "python_breakdown": {"compile": 0.5},
        "mismatch": False,
    }
    assert extra["returncode"] == 0
    assert extra["peak_reset"] is None


def test_the_collector_is_chosen_in_setup_and_recorded_in_dims(
    cli: FakeCli, ctx: Context, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(lifecycle, "CgroupScope", FakeScope)
    bench = _instance("lifecycle.compile.warm", ctx)
    bench.setup(ctx)
    assert ctx.dims == {"collector": "cgroup"}
    # A later change of the host does not reach the samples.
    monkeypatch.setattr(FakeScope, "available", staticmethod(lambda: "gone"))
    bench.sample(ctx)
    assert isinstance(cli.calls[-1].kwargs["scope"], FakeScope)
    assert cli.calls[-1].kwargs["sample_memory"] is False


def test_compile_warm_reuses_the_primed_app(cli: FakeCli, ctx: Context):
    _run(_instance("lifecycle.compile.warm", ctx), ctx)
    web = ctx.cache_dir / "app" / ".web"
    web.mkdir()
    _run(_instance("lifecycle.compile.warm", ctx), ctx)
    assert web.is_dir()


def test_compile_incremental_rewrites_the_leaf_marker(cli: FakeCli, ctx: Context):
    bench = _instance("lifecycle.compile.incremental", ctx)
    bench.setup_cache(ctx)
    bench.setup(ctx)
    marker = ctx.cache_dir / "app" / "playground" / "components" / "marker.py"
    original = marker.read_text(encoding="utf-8")
    markers = []
    for _ in range(3):
        bench.prepare(ctx)
        result = bench.sample(ctx)
        value = _extra(result)["marker"]
        assert re.fullmatch(r"m-\d+-leaf", value)
        assert marker.read_text(encoding="utf-8") == original.replace(
            'LEAF_MARKER = "m-initial-leaf"  # bench:hmr-target leaf',
            f'LEAF_MARKER = "{value}"  # bench:hmr-target leaf',
        )
        markers.append(value)
        # conclude restores the cached app to the fixture its stamp describes.
        bench.conclude(ctx)
        assert marker.read_text(encoding="utf-8") == original
    assert len(set(markers)) == 3
    assert [call.args for call in cli.calls] == [["compile"]] * 4


def test_the_arms_of_an_aa_run_make_distinct_edits(cli: FakeCli, ctx: Context):
    arms = [_instance("lifecycle.compile.incremental", ctx) for _ in "AB"]
    arms[0].setup_cache(ctx)
    for arm in arms:
        arm.setup(ctx)
    markers = []
    for _ in range(2):
        for arm in arms:
            arm.prepare(ctx)
            markers.append(_extra(arm.sample(ctx))["marker"])
            arm.conclude(ctx)
    assert len(set(markers)) == 4


def test_exports(cli: FakeCli, ctx: Context):
    for mode in ("dev", "prod"):
        bench = _instance(f"lifecycle.export.{mode}", ctx)
        bench.setup_cache(ctx)
        bench.setup(ctx)
        dest = ctx.workdir / "export"
        dest.mkdir(exist_ok=True)
        (dest / "frontend.zip").write_bytes(b"old")
        bench.prepare(ctx)
        # reflex needs the destination to exist, and the old zips are gone.
        assert dest.is_dir()
        assert list(dest.iterdir()) == []
        bench.sample(ctx)
        assert cli.calls[-1].args == [
            "export",
            "--env",
            mode,
            "--zip-dest-dir",
            str(dest),
        ]
        assert cli.calls[-1].cwd == ctx.cache_dir / "app"


@pytest.mark.parametrize(
    ("bench_id", "mode", "backend_only"),
    [
        ("lifecycle.run.dev.ready", "dev", False),
        ("lifecycle.run.prod.ready", "prod", False),
        ("lifecycle.run.preview.ready", "preview", False),
        ("lifecycle.run.backend_only.ready", "dev", True),
    ],
)
def test_run_ready(
    cli: FakeCli, ctx: Context, bench_id: str, mode: str, backend_only: bool
):
    bench = _instance(bench_id, ctx)
    (result,) = _run(bench, ctx)
    (app,) = FakeApp.started
    assert app.app_dir == ctx.cache_dir / "app"
    assert app.kwargs["mode"] == mode
    assert app.kwargs["backend_only"] is backend_only
    assert app.kwargs["reflex_version"] == ctx.subject.reflex_version
    assert app.kwargs["env"]["REFLEX_DIR"] == str(ctx.subject_cache_dir / "reflex")
    assert app.stopped
    assert result.values == {"process_ready": 1.25, "http_ready": 1.5}
    assert result.extra == {
        "readiness": {
            "spawned": 0.01,
            "ready_line": 1.0,
            "process_ready": 1.25,
            "http_ready": 1.5,
            "interactive_ready": None,
        }
    }
    assert ctx.fixture == fixtures.describe_playground()
    assert ctx.dims == {}


def test_conclude_stops_the_app_when_the_sample_raised(cli: FakeCli, ctx: Context):
    bench = _instance("lifecycle.run.prod.ready", ctx)
    bench.setup_cache(ctx)
    bench.setup(ctx)
    FakeApp.fail_start = True
    bench.prepare(ctx)
    with pytest.raises(AppStartError):
        bench.sample(ctx)
    bench.conclude(ctx)
    (app,) = FakeApp.started
    assert app.stopped


def test_conclude_stops_the_app_before_a_late_sample_can_start_it(
    cli: FakeCli, ctx: Context
):
    # conclude runs on a fresh thread after a timeout; the app it stops is the
    # one sample would start, so nothing starts after it.
    bench = _instance("lifecycle.run.dev.ready", ctx)
    bench.setup_cache(ctx)
    bench.setup(ctx)
    bench.prepare(ctx)
    bench.conclude(ctx)
    with pytest.raises(AppStartError, match="stopped before it started"):
        bench.sample(ctx)
    assert FakeApp.started[0].stopped


def test_import(cli: FakeCli, ctx: Context):
    bench = _instance("lifecycle.import", ctx)
    result = bench.sample(ctx)
    (call,) = cli.calls
    assert call.args == []
    assert call.kwargs["prefix"] == ("-c", lifecycle.IMPORT)
    # import reflex alone is lazy; the attributes load the framework.
    assert lifecycle.IMPORT == "import reflex as rx; rx.App; rx.State"
    assert call.cwd == ctx.workdir
    assert call.env == ctx.env
    assert not call.kwargs.get("phases")
    assert result == {"wall": 2.5}


@pytest.mark.parametrize("pages", [1, 10])
def test_scale_compile_warm(cli: FakeCli, ctx: Context, pages: int):
    bench = _instance("lifecycle.scale.compile.warm", ctx, pages=pages)
    _run(bench, ctx)
    params = generate.GenParams(pages=pages)
    assert ctx.fixture == generate.describe(params)
    assert (
        len(list((ctx.cache_dir / "app" / "genapp" / "pages").glob("page_*.py")))
        == pages
    )
    prime, sample = cli.calls
    assert prime.args == sample.args == ["compile"]
    assert sample.cwd == ctx.cache_dir / "app"
    assert sample.kwargs["timeout"] == lifecycle.QUICK_S


def test_the_1000_page_tier_gets_the_long_timeout(cli: FakeCli, ctx: Context):
    bench = _instance("lifecycle.scale.compile.warm", ctx, pages=1000)
    bench.setup(ctx)
    bench.sample(ctx)
    assert cli.calls[-1].kwargs["timeout"] == lifecycle.SLOW_S


def test_scale_hidden_params_shape_the_app(cli: FakeCli, ctx: Context):
    bench = _instance("lifecycle.scale.compile.warm", ctx, pages=1, state_vars=3)
    _run(bench, ctx)
    assert ctx.fixture is not None
    assert ctx.fixture["params"]["state_vars"] == 3


def test_scale_compile_incremental_edits_the_first_leaf_target(
    cli: FakeCli, ctx: Context
):
    bench = _instance("lifecycle.scale.compile.incremental", ctx, pages=10)
    bench.setup_cache(ctx)
    bench.setup(ctx)
    app = ctx.cache_dir / "app"
    manifest = json.loads((app / generate.MANIFEST).read_text(encoding="utf-8"))
    first = next(t for t in manifest["targets"] if t["name"].startswith("leaf-"))
    bench.prepare(ctx)
    marker = _extra(bench.sample(ctx))["marker"]
    assert re.fullmatch(rf"m-\d+-{first['name']}", marker)
    text = (app / first["path"]).read_text(encoding="utf-8")
    assert f'"{marker}"  # bench:hmr-target {first["name"]}' in text


def test_the_host_bun_is_hidden(cli: FakeCli, ctx: Context, tmp_path: Path):
    # reflex takes a bun from PATH when REFLEX_DIR has none: a host bun would
    # make a cold init warm.
    tools, venv, system = tmp_path / "tools", tmp_path / "venv", tmp_path / "system"
    for directory in (tools, venv, system):
        directory.mkdir()
    for name in ("bun", "bunx", "node", "unzip"):
        (tools / name).write_text("#!/bin/sh\n", encoding="utf-8")
        (tools / name).chmod(0o755)
    (system / "git").write_text("#!/bin/sh\n", encoding="utf-8")
    ctx.env["PATH"] = os.pathsep.join([str(venv), str(tools), str(system)])
    bench = _instance("lifecycle.init.cold", ctx)
    _run(bench, ctx)
    first, view, last = cli.calls[0].env["PATH"].split(os.pathsep)
    assert (first, last) == (str(venv), str(system))
    assert Path(view).is_relative_to(ctx.workdir)
    assert sorted(path.name for path in Path(view).iterdir()) == ["node", "unzip"]
    assert (Path(view) / "node").resolve() == (tools / "node").resolve()
