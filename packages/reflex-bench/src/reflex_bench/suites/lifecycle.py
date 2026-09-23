"""Lifecycle benchmarks: how long a user waits for init, compile, export, run and import.

Every benchmark starts reflex as a user does, through the app driver, and the
harness owns every cache reflex reads, so no cache of the host or of CI reaches
a measured phase:

====================  =============================  ======================  =========================
State                 ``REFLEX_DIR`` (bun,           ``BUN_INSTALL_CACHE_    app and ``.web``
                      templates)                     DIR``                   (``node_modules``)
====================  =============================  ======================  =========================
``init.cold``         fresh per sample               untouched               fresh empty directory
``init.warm``         ``ctx.cache_dir/reflex``,      untouched               fresh empty directory
                      primed
``compile.cold``      ``ctx.cache_dir/reflex``,      fresh per sample        fresh copy per sample
                      primed
all others            ``ctx.cache_dir/reflex``,      host default            ``ctx.cache_dir/app``,
                      primed                                                 primed by one compile
====================  =============================  ======================  =========================

When its ``REFLEX_DIR`` holds no bun, reflex takes one from ``PATH`` if it is
new enough (1.3 for reflex 0.8.23, 1.4 for 0.9), so a host bun would make a
cold start warm and make versions run different buns. Commands run with each
``PATH`` directory holding a bun replaced by a view of everything else in it.

The ``time`` benchmarks report ``wall`` (from just before the spawn to the end
of the command, without the harness's own overhead), ``cpu`` and ``peak_mem``
of the whole process tree, from a cgroup scope where the host has them, else
from the reaped children and PSS sampling (``cpu_method``, ``memory_method``).
Whole-run peaks only: per-phase peaks need Linux 6.12. Samples are taken with
``phases=True``: its ``--loglevel debug`` costs 0.04 % of a warm playground
compile (median of 10 ABBA pairs against ``--loglevel info``, 1.1013 s against
1.1009 s), below the 2 % above which phases would come from a separate untimed
compile. The process tree and PSS samplers add another 3 % locally, the same
in both arms of a comparison.

``export`` rebuilds and zips the frontend every time: after priming, the first
and second exports of the playground differ by 5 % (HEAD) to 8 % (0.8.23), and
the second installs no packages, so a sample measures the steady state: a
primed app whose previous export is replaced.

The ``lifecycle.scale.*`` tiers drive generated apps
(:mod:`reflex_bench.fixtures.generate`) of 1 to 1000 pages. Suites are chosen
per benchmark, not per instance, so the tiers have ids of their own instead of
``lifecycle.compile.*[app=gen,pages=N]``.
"""

from __future__ import annotations

import dataclasses
import functools
import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

from reflex_bench.collectors.cgroup import CgroupScope
from reflex_bench.context import Context
from reflex_bench.drivers.app_process import AppProcess, Mode, cache_env, run_cli
from reflex_bench.fixtures import (
    bump_marker,
    describe_playground,
    ensure_fixture,
    generate,
    materialize_playground,
)
from reflex_bench.fixtures.generate import GenParams
from reflex_bench.registry import Metric, SampleResult, benchmark
from reflex_bench.schema import FixtureDoc

# Command timeouts; each hook gets MARGIN_S more, so a stuck command is killed
# by the driver and reported before the scheduler abandons the hook.
QUICK_S = 90.0
SLOW_S = 570.0
PRIME_S = 870.0
MARGIN_S = 30.0
# The wait for GET / once the app is process-ready; within MARGIN_S.
HTTP_S = 20.0

INIT = ["init", "--template", "blank"]
PLAYGROUND = {"app": ["playground"]}
PAGES = {"pages": [1, 10, 100, 1000]}
GEN_HIDDEN = {
    field.name: field.default
    for field in dataclasses.fields(GenParams)
    if field.name != "pages"
}
TIME = {
    "wall": Metric(
        unit="s",
        direction="lower",
        description="From just before the spawn to the end of the command.",
    ),
    "cpu": Metric(
        unit="s", direction="lower", description="CPU time of the process tree."
    ),
    "peak_mem": Metric(
        unit="B", direction="lower", description="Peak memory of the process tree."
    ),
}
STARTUP = {
    "process_ready": Metric(
        unit="s",
        direction="lower",
        description="From the spawn to the ready lines, with every port accepting TCP.",
    ),
    "http_ready": Metric(
        unit="s",
        direction="lower",
        description="From the spawn to GET / (/ping without a frontend) answering 200.",
    ),
}
_BUN = ("bun", "bunx")


def _hide_bun(path: str, views: Path) -> str:
    """Replace the ``PATH`` directories holding a bun with views of everything else in them.

    Args:
        path: A ``PATH`` value.
        views: Where to create the views: links to each other entry of a directory.

    Returns:
        The new ``PATH`` value.
    """
    entries = []
    for entry in path.split(os.pathsep):
        directory = Path(entry)
        if not (entry and any((directory / name).is_file() for name in _BUN)):
            entries.append(entry)
            continue
        view = views / hashlib.sha256(entry.encode()).hexdigest()[:16]
        if not view.is_dir():
            view.mkdir(parents=True)
            for item in directory.iterdir():
                if item.name not in _BUN:
                    (view / item.name).symlink_to(item.absolute())
        entries.append(str(view))
    return os.pathsep.join(entries)


def _env(
    ctx: Context, *, reflex_dir: Path | None = None, bun_cache: Path | None = None
) -> dict[str, str]:
    """Build the environment of a benchmark's reflex commands.

    Args:
        ctx: The benchmark context.
        reflex_dir: ``REFLEX_DIR``; ``ctx.cache_dir / "reflex"`` by default.
        bun_cache: ``BUN_INSTALL_CACHE_DIR``; the host's by default.

    Returns:
        ``ctx.env`` with the cache directories set and no bun on ``PATH``.
    """
    env = {
        **ctx.env,
        **cache_env(
            reflex_dir=reflex_dir or ctx.cache_dir / "reflex", bun_cache=bun_cache
        ),
    }
    env["PATH"] = _hide_bun(env.get("PATH", ""), ctx.workdir / "path")
    return env


def _size(path: Path) -> int:
    """Count the bytes of the files in a directory tree.

    Args:
        path: The directory.

    Returns:
        The sum of the file sizes, links not followed; 0 when it is missing.
    """
    return sum(
        (Path(root) / name).lstat().st_size
        for root, _, files in os.walk(path)
        for name in files
    )


def _remove(*paths: Path) -> None:
    """Delete the directory trees that exist.

    Args:
        *paths: The directories.
    """
    for path in paths:
        if path.exists():
            shutil.rmtree(path)


def _run(ctx: Context, args: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    """Run an untimed reflex command, e.g. to prime a cache.

    Args:
        ctx: The benchmark context.
        args: The reflex arguments.
        cwd: The app directory.
        env: The environment.
    """
    run_cli(ctx.subject.python, args, cwd=cwd, env=env, timeout=PRIME_S).check()


def _prime_reflex_dir(ctx: Context) -> None:
    """Fill the cache directory's ``REFLEX_DIR`` (bun, templates) with an untimed init.

    Args:
        ctx: The benchmark context.
    """
    scratch = ctx.workdir / "prime"
    scratch.mkdir(exist_ok=True)
    try:
        _run(ctx, INIT, cwd=scratch, env=_env(ctx))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def _timed(
    ctx: Context,
    args: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: float,
    **extra: Any,
) -> SampleResult:
    """Run a reflex command and measure its whole process tree.

    Args:
        ctx: The benchmark context.
        args: The reflex arguments.
        cwd: The app directory.
        env: The environment.
        timeout: Seconds before the command is killed.
        **extra: More extra data for the sample.

    Returns:
        Wall, CPU and peak memory, with the phase attribution, the collectors'
        methods and ``extra`` as extra data.

    Raises:
        RuntimeError: When the command fails or no collector measured its memory.
    """
    scope = CgroupScope() if CgroupScope.available() is None else None
    result = run_cli(
        ctx.subject.python,
        args,
        cwd=cwd,
        env=env,
        timeout=timeout,
        scope=scope,
        phases=True,
        sample_memory=scope is None,
    ).check()
    if result.peak_mem_bytes is None:
        msg = f"no memory collector measured reflex {' '.join(args)}"
        raise RuntimeError(msg)
    return SampleResult(
        {"wall": result.wall_s, "cpu": result.cpu_s, "peak_mem": result.peak_mem_bytes},
        extra={
            "phases": result.attribution(),
            "timing": result.timing,
            "cpu_method": result.cpu_method,
            "memory_method": result.memory_method,
            "peak_reset": None if result.cgroup is None else result.cgroup.peak_reset,
            "returncode": result.returncode,
            **extra,
        },
    )


def _gen_params(ctx: Context) -> GenParams:
    """Read the generator parameters of a scaling tier.

    Args:
        ctx: The benchmark context.

    Returns:
        ``pages`` and the hidden parameters, as generator parameters.
    """
    return GenParams(**{
        f.name: ctx.params[f.name] for f in dataclasses.fields(GenParams)
    })


@benchmark(
    id="lifecycle.init.cold",
    suites=("daily",),
    metrics=TIME,
    timeout=QUICK_S + MARGIN_S,
    estimate=4,
)
class InitCold:
    """`reflex init --template blank` with a fresh REFLEX_DIR: bun is downloaded (network-bound)."""

    env: dict[str, str]
    deleted: dict[str, int]

    def setup(self, ctx: Context) -> None:
        """Point REFLEX_DIR into the work directory.

        Args:
            ctx: The benchmark context.
        """
        self.env = _env(ctx, reflex_dir=ctx.workdir / "reflex")

    def prepare(self, ctx: Context) -> None:
        """Delete the previous sample's app and REFLEX_DIR, measuring them first.

        Args:
            ctx: The benchmark context.
        """
        app, reflex_dir = ctx.workdir / "app", ctx.workdir / "reflex"
        self.deleted = {"web": _size(app / ".web"), "reflex_dir": _size(reflex_dir)}
        _remove(app, reflex_dir)
        app.mkdir()

    def sample(self, ctx: Context) -> SampleResult:
        """Initialize the app.

        Args:
            ctx: The benchmark context.

        Returns:
            The measurements, with the bytes deleted before the sample.
        """
        return _timed(
            ctx,
            INIT,
            cwd=ctx.workdir / "app",
            env=self.env,
            timeout=QUICK_S,
            deleted_bytes=self.deleted,
        )


@benchmark(
    id="lifecycle.init.warm",
    suites=("daily",),
    metrics=TIME,
    timeout=QUICK_S + MARGIN_S,
    setup_timeout=PRIME_S + MARGIN_S,
    estimate=1,
)
class InitWarm:
    """`reflex init --template blank` in an empty directory, with bun and the templates in REFLEX_DIR."""

    env: dict[str, str]

    def setup_cache(self, ctx: Context) -> None:
        """Fill REFLEX_DIR.

        Args:
            ctx: The benchmark context.
        """
        _prime_reflex_dir(ctx)

    def setup(self, ctx: Context) -> None:
        """Build the environment.

        Args:
            ctx: The benchmark context.
        """
        self.env = _env(ctx)

    def prepare(self, ctx: Context) -> None:
        """Replace the previous sample's app with an empty directory.

        Args:
            ctx: The benchmark context.
        """
        _remove(ctx.workdir / "app")
        (ctx.workdir / "app").mkdir()

    def sample(self, ctx: Context) -> SampleResult:
        """Initialize the app.

        Args:
            ctx: The benchmark context.

        Returns:
            The measurements.
        """
        return _timed(ctx, INIT, cwd=ctx.workdir / "app", env=self.env, timeout=QUICK_S)


@benchmark(
    id="lifecycle.compile.cold",
    suites=("daily",),
    params=PLAYGROUND,
    metrics=TIME,
    timeout=SLOW_S + MARGIN_S,
    setup_timeout=PRIME_S + MARGIN_S,
    estimate=10,
)
class CompileCold:
    """`reflex compile` of a fresh copy with an empty bun cache: template copy, package install, compile."""

    env: dict[str, str]
    deleted: dict[str, int]

    def setup_cache(self, ctx: Context) -> None:
        """Fill REFLEX_DIR.

        Args:
            ctx: The benchmark context.
        """
        _prime_reflex_dir(ctx)

    def setup(self, ctx: Context) -> None:
        """Point bun's package cache into the work directory.

        Args:
            ctx: The benchmark context.
        """
        ctx.fixture = describe_playground()
        self.env = _env(ctx, bun_cache=ctx.workdir / "bun-cache")

    def prepare(self, ctx: Context) -> None:
        """Replace the previous sample's app and bun cache with a fresh copy, measuring them first.

        Args:
            ctx: The benchmark context.
        """
        app, bun_cache = ctx.workdir / "app", ctx.workdir / "bun-cache"
        self.deleted = {"web": _size(app / ".web"), "bun_cache": _size(bun_cache)}
        _remove(app, bun_cache)
        materialize_playground(app)

    def sample(self, ctx: Context) -> SampleResult:
        """Compile the app.

        Args:
            ctx: The benchmark context.

        Returns:
            The measurements, with the bytes deleted before the sample.
        """
        return _timed(
            ctx,
            ["compile"],
            cwd=ctx.workdir / "app",
            env=self.env,
            timeout=SLOW_S,
            deleted_bytes=self.deleted,
        )


class _Primed:
    """The playground in the cache directory, primed by one untimed compile.

    ``sample`` compiles it, after giving ``edit``'s hot reload target a new
    string when set.
    """

    app_dir: Path
    env: dict[str, str]
    edit: tuple[Path, str] | None = None
    marker: str | None = None

    def describe(self, ctx: Context) -> FixtureDoc:
        """Describe the app.

        Args:
            ctx: The benchmark context.

        Returns:
            The playground's description.
        """
        return describe_playground()

    def make(self, ctx: Context, dest: Path) -> FixtureDoc:
        """Write the app.

        Args:
            ctx: The benchmark context.
            dest: The new app directory.

        Returns:
            The app's description.
        """
        return materialize_playground(dest)

    def timeout(self, ctx: Context) -> float:
        """Give the timeout of one compile.

        Args:
            ctx: The benchmark context.

        Returns:
            Seconds.
        """
        return QUICK_S

    def setup_cache(self, ctx: Context) -> None:
        """Copy the app unless its copy is current, then prime it (REFLEX_DIR, .web, packages).

        Args:
            ctx: The benchmark context.
        """
        app, _ = ensure_fixture(
            ctx.cache_dir,
            functools.partial(self.describe, ctx),
            functools.partial(self.make, ctx),
        )
        _run(ctx, ["compile"], cwd=app, env=_env(ctx))

    def setup(self, ctx: Context) -> None:
        """Record the fixture and build the environment.

        Args:
            ctx: The benchmark context.
        """
        ctx.fixture = self.describe(ctx)
        self.app_dir = ctx.cache_dir / "app"
        self.env = _env(ctx)

    def prepare(self, ctx: Context) -> None:
        """Give the edited hot reload target, if any, a new string.

        Args:
            ctx: The benchmark context.
        """
        if self.edit is not None:
            self.marker = bump_marker(*self.edit)

    def sample(self, ctx: Context) -> SampleResult:
        """Compile the app.

        Args:
            ctx: The benchmark context.

        Returns:
            The measurements, with the new string of the edited target.
        """
        edited = {} if self.marker is None else {"marker": self.marker}
        return _timed(
            ctx,
            ["compile"],
            cwd=self.app_dir,
            env=self.env,
            timeout=self.timeout(ctx),
            **edited,
        )


@benchmark(
    id="lifecycle.compile.warm",
    suites=("pr", "daily"),
    params=PLAYGROUND,
    metrics=TIME,
    warmup=1,
    timeout=QUICK_S + MARGIN_S,
    setup_timeout=PRIME_S + MARGIN_S,
    estimate=1.3,
)
class CompileWarm(_Primed):
    """`reflex compile` of the primed playground, unchanged since the last compile."""


@benchmark(
    id="lifecycle.compile.incremental",
    suites=("pr", "daily"),
    params=PLAYGROUND,
    metrics=TIME,
    warmup=1,
    timeout=QUICK_S + MARGIN_S,
    setup_timeout=PRIME_S + MARGIN_S,
    estimate=1.3,
)
class CompileIncremental(_Primed):
    """`reflex compile` of the primed playground after an edit of the leaf component."""

    def setup(self, ctx: Context) -> None:
        """Pick the leaf hot reload target of the playground.

        Args:
            ctx: The benchmark context.
        """
        super().setup(ctx)
        self.edit = (self.app_dir / "playground" / "components" / "marker.py", "leaf")


class _Export(_Primed):
    """``reflex export`` of the primed playground, zipped into the work directory."""

    mode: str

    def prepare(self, ctx: Context) -> None:
        """Replace the previous zips with an empty directory; reflex needs it to exist.

        Args:
            ctx: The benchmark context.
        """
        _remove(ctx.workdir / "export")
        (ctx.workdir / "export").mkdir()

    def sample(self, ctx: Context) -> SampleResult:
        """Export the app.

        Args:
            ctx: The benchmark context.

        Returns:
            The measurements.
        """
        args = [
            "export",
            "--env",
            self.mode,
            "--zip-dest-dir",
            str(ctx.workdir / "export"),
        ]
        return _timed(ctx, args, cwd=self.app_dir, env=self.env, timeout=QUICK_S)


@benchmark(
    id="lifecycle.export.dev",
    suites=("daily",),
    params=PLAYGROUND,
    metrics=TIME,
    warmup=1,
    timeout=QUICK_S + MARGIN_S,
    setup_timeout=PRIME_S + MARGIN_S,
    estimate=7,
)
class ExportDev(_Export):
    """`reflex export --env dev` of the primed playground: frontend build and both zips."""

    mode = "dev"


@benchmark(
    id="lifecycle.export.prod",
    suites=("daily",),
    params=PLAYGROUND,
    metrics=TIME,
    warmup=1,
    timeout=QUICK_S + MARGIN_S,
    setup_timeout=PRIME_S + MARGIN_S,
    estimate=7,
)
class ExportProd(_Export):
    """`reflex export --env prod` of the primed playground: frontend build and both zips."""

    mode = "prod"


class _Ready(_Primed):
    """``reflex run`` of the primed playground until it answers HTTP; conclude stops it."""

    mode: Mode = "dev"
    backend_only = False
    start_timeout = QUICK_S
    app: AppProcess | None = None

    def sample(self, ctx: Context) -> SampleResult:
        """Start the app and wait for tiers 1 (process-ready) and 2 (HTTP-ready).

        Args:
            ctx: The benchmark context.

        Returns:
            Seconds from the spawn to each tier, with the readiness as extra data.
        """
        # conclude() may run on another thread after a timeout and clear self.app.
        app = self.app = AppProcess(
            ctx.subject.python,
            self.app_dir,
            mode=self.mode,
            reflex_version=ctx.subject.reflex_version,
            env=self.env,
            backend_only=self.backend_only,
            start_timeout=self.start_timeout,
        )
        readiness = app.start()
        http_ready = app.wait_http_ready(timeout=HTTP_S)
        return SampleResult(
            {"process_ready": readiness.process_ready, "http_ready": http_ready},
            extra={"readiness": dataclasses.asdict(readiness)},
        )

    def conclude(self, ctx: Context) -> None:
        """Kill the app's process tree, also after a failed or timed-out sample.

        Args:
            ctx: The benchmark context.
        """
        if self.app is not None:
            self.app.stop()
            self.app = None


@benchmark(
    id="lifecycle.run.dev.ready",
    suites=("daily",),
    kind="startup",
    params=PLAYGROUND,
    metrics=STARTUP,
    warmup=1,
    timeout=QUICK_S + MARGIN_S,
    setup_timeout=PRIME_S + MARGIN_S,
    estimate=4,
)
class RunDevReady(_Ready):
    """`reflex run --env dev` of the primed playground until the Vite dev server answers GET /."""


@benchmark(
    id="lifecycle.run.prod.ready",
    suites=("daily",),
    kind="startup",
    params=PLAYGROUND,
    metrics=STARTUP,
    warmup=1,
    timeout=SLOW_S + MARGIN_S,
    setup_timeout=PRIME_S + MARGIN_S,
    estimate=8,
)
class RunProdReady(_Ready):
    """`reflex run --env prod` of the primed playground: compile, frontend build and start."""

    mode = "prod"
    start_timeout = SLOW_S


@benchmark(
    id="lifecycle.run.preview.ready",
    suites=("daily",),
    kind="startup",
    params=PLAYGROUND,
    metrics=STARTUP,
    warmup=1,
    timeout=SLOW_S + MARGIN_S,
    setup_timeout=PRIME_S + MARGIN_S,
    estimate=6,
    min_version="0.9.8",
)
class RunPreviewReady(_Ready):
    """`reflex run --env preview` of the primed playground: an unminified build, then start."""

    mode = "preview"
    start_timeout = SLOW_S


@benchmark(
    id="lifecycle.run.backend_only.ready",
    suites=("daily",),
    kind="startup",
    params=PLAYGROUND,
    metrics=STARTUP,
    warmup=1,
    timeout=QUICK_S + MARGIN_S,
    setup_timeout=PRIME_S + MARGIN_S,
    estimate=2,
)
class RunBackendOnlyReady(_Ready):
    """`reflex run --backend-only` of the primed playground until /ping answers: the scale-to-zero start."""

    backend_only = True


@benchmark(
    id="lifecycle.import",
    suites=("daily",),
    metrics={
        "wall": Metric(
            unit="s",
            direction="lower",
            description="A fresh interpreter importing reflex.",
        )
    },
    warmup=1,
    timeout=QUICK_S + MARGIN_S,
    estimate=0.03,
)
class Import:
    """`python -c "import reflex"` in a fresh interpreter."""

    def sample(self, ctx: Context) -> dict[str, float]:
        """Import reflex once.

        Args:
            ctx: The benchmark context.

        Returns:
            The wall time of the interpreter.
        """
        result = run_cli(
            ctx.subject.python,
            [],
            cwd=ctx.workdir,
            env=ctx.env,
            timeout=QUICK_S,
            prefix=("-c", "import reflex"),
        ).check()
        return {"wall": result.wall_s}


class _Generated(_Primed):
    """A generated app of the tier's GenParams instead of the playground."""

    def describe(self, ctx: Context) -> FixtureDoc:
        """Describe the app.

        Args:
            ctx: The benchmark context.

        Returns:
            The generated app's description.
        """
        return generate.describe(_gen_params(ctx))

    def make(self, ctx: Context, dest: Path) -> FixtureDoc:
        """Write the app.

        Args:
            ctx: The benchmark context.
            dest: The new app directory.

        Returns:
            The app's description.
        """
        return generate.generate(dest, _gen_params(ctx))

    def timeout(self, ctx: Context) -> float:
        """Give the timeout of one compile, which grows with the tier.

        Args:
            ctx: The benchmark context.

        Returns:
            Seconds.
        """
        return SLOW_S if ctx.params["pages"] >= 1000 else QUICK_S


@benchmark(
    id="lifecycle.scale.compile.warm",
    params=PAGES,
    hidden_params=GEN_HIDDEN,
    metrics=TIME,
    warmup=1,
    timeout=SLOW_S + MARGIN_S,
    setup_timeout=PRIME_S + MARGIN_S,
    estimate=18,
)
class ScaleCompileWarm(_Generated):
    """`reflex compile` of a primed generated app, unchanged since the last compile."""


@benchmark(
    id="lifecycle.scale.compile.incremental",
    params=PAGES,
    hidden_params=GEN_HIDDEN,
    metrics=TIME,
    warmup=1,
    timeout=SLOW_S + MARGIN_S,
    setup_timeout=PRIME_S + MARGIN_S,
    estimate=18,
)
class ScaleCompileIncremental(_Generated):
    """`reflex compile` of a primed generated app after an edit of its first leaf target."""

    def setup(self, ctx: Context) -> None:
        """Pick the first leaf target of the app's manifest.

        Args:
            ctx: The benchmark context.
        """
        super().setup(ctx)
        manifest = json.loads(
            (self.app_dir / generate.MANIFEST).read_text(encoding="utf-8")
        )
        leaf = next(t for t in manifest["targets"] if t["name"].startswith("leaf-"))
        self.edit = (self.app_dir / leaf["path"], leaf["name"])
