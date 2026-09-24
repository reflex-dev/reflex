"""Lifecycle benchmarks: how long a user waits for init, compile, export, run and import.

Every benchmark starts reflex as a user does, through the app driver, and the
harness owns every cache reflex reads, so no cache of the host or of CI reaches
a measured phase:

====================  =============================  ======================  =========================
State                 ``REFLEX_DIR`` (bun,           ``BUN_INSTALL_CACHE_    app and ``.web``
                      templates)                     DIR``                   (``node_modules``)
====================  =============================  ======================  =========================
``init.cold``         fresh per sample               untouched               fresh empty directory
``init.warm``         shared, primed                 untouched               fresh empty directory
``compile.cold``      shared, primed                 fresh per sample        fresh copy per sample
all others            shared, primed                 host default            ``ctx.cache_dir/app``,
                                                                             primed by one compile
====================  =============================  ======================  =========================

The shared ``REFLEX_DIR`` is ``ctx.subject_cache_dir / "reflex"``, one per
subject: the first instance that needs it downloads bun, the others find it.

When its ``REFLEX_DIR`` holds no bun, reflex takes one from ``PATH`` if it is
new enough (1.3 for reflex 0.8.23, 1.4 for 0.9), so a host bun would make a
cold start warm and make versions run different buns. Commands run with each
``PATH`` directory holding a bun replaced by a view of everything else in it.

The ``time`` benchmarks report ``wall`` (from just before the spawn to the end
of the command, without the harness's own overhead), ``cpu`` and ``peak_mem``
of the whole process tree, from a cgroup scope where the host has them, else
from the reaped children and PSS sampling. The collector is chosen once per
instance and recorded in ``dims`` (``collector: cgroup | fallback``), so the
two never share a series. Whole-run peaks only: per-phase peaks need Linux
6.12. Samples are taken with ``phases=True``: its ``--loglevel debug`` costs
0.04 % of a warm playground compile (n = 10 per arm, interleaved ABBA against
``--loglevel info``: medians 1.1013 s and 1.1009 s), below the 2 % above which
phases would come from a separate untimed compile. The process tree and PSS
samplers add another 3 % locally, the same in both arms of a comparison.

``export`` rebuilds the frontend and writes both zips every time: after
priming, the first two exports of the playground are within 2 to 8 % of each
other and neither installs packages, so a sample measures the steady state, a
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
import itertools
import json
import os
import shutil
from collections.abc import Callable
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
# import reflex alone is lazy; the two attributes load the framework.
IMPORT = "import reflex as rx; rx.App; rx.State"
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
# Numbers the hot reload edits, unique across the arms of one process.
_EDITS = itertools.count(1)

_daily = functools.partial(
    benchmark,
    suites=("daily",),
    metrics=TIME,
    timeout=QUICK_S + MARGIN_S,
    setup_timeout=PRIME_S + MARGIN_S,
)
_playground = functools.partial(_daily, params=PLAYGROUND, warmup=1)
_ready = functools.partial(_playground, kind="startup", metrics=STARTUP)
_scale = functools.partial(
    benchmark,
    params=PAGES,
    hidden_params=GEN_HIDDEN,
    metrics=TIME,
    warmup=1,
    timeout=SLOW_S + MARGIN_S,
    setup_timeout=PRIME_S + MARGIN_S,
    estimate=18,
)


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
        reflex_dir: ``REFLEX_DIR``; the subject's shared one by default.
        bun_cache: ``BUN_INSTALL_CACHE_DIR``; the host's by default.

    Returns:
        ``ctx.env`` with the cache directories set and no bun on ``PATH``.
    """
    env = {
        **ctx.env,
        **cache_env(
            reflex_dir=reflex_dir or ctx.subject_cache_dir / "reflex",
            bun_cache=bun_cache,
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
    """Fill the subject's shared ``REFLEX_DIR`` (bun, templates) with an untimed init.

    Nothing runs when it already holds a bun: one download per subject.

    Args:
        ctx: The benchmark context.
    """
    if (ctx.subject_cache_dir / "reflex" / "bun" / "bin" / "bun").is_file():
        return
    scratch = ctx.workdir / "prime"
    scratch.mkdir(exist_ok=True)
    try:
        _run(ctx, INIT, cwd=scratch, env=_env(ctx))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def _record_collector(ctx: Context) -> None:
    """Choose the collector of a ``time`` benchmark once and record it in ``dims``.

    Args:
        ctx: The benchmark context.
    """
    ctx.dims["collector"] = "cgroup" if CgroupScope.available() is None else "fallback"


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
    scope = CgroupScope() if ctx.dims["collector"] == "cgroup" else None
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


@_daily(id="lifecycle.init.cold", estimate=4)
class InitCold:
    """`reflex init --template blank` with a fresh REFLEX_DIR: bun is downloaded (network-bound)."""

    env: dict[str, str]
    deleted: dict[str, int]

    def setup(self, ctx: Context) -> None:
        """Point REFLEX_DIR into the work directory.

        Args:
            ctx: The benchmark context.
        """
        _record_collector(ctx)
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


@_daily(id="lifecycle.init.warm", estimate=1)
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
        _record_collector(ctx)
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


@_daily(
    id="lifecycle.compile.cold",
    params=PLAYGROUND,
    timeout=SLOW_S + MARGIN_S,
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
        _record_collector(ctx)
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
    """An app in the cache directory, primed by one untimed compile."""

    app_dir: Path
    env: dict[str, str]

    def fixture(
        self, ctx: Context
    ) -> tuple[Callable[[], FixtureDoc], Callable[[Path], object]]:
        """Choose the app.

        Args:
            ctx: The benchmark context.

        Returns:
            How to describe it and how to write it, as :func:`ensure_fixture`
            takes them: the playground's.
        """
        return describe_playground, materialize_playground

    def setup_cache(self, ctx: Context) -> None:
        """Write the app unless its copy is current, then prime it (REFLEX_DIR, .web, packages).

        Args:
            ctx: The benchmark context.
        """
        app = ensure_fixture(ctx.cache_dir, *self.fixture(ctx))
        _run(ctx, ["compile"], cwd=app, env=_env(ctx))

    def setup(self, ctx: Context) -> None:
        """Record the fixture and build the environment.

        Args:
            ctx: The benchmark context.
        """
        describe, _ = self.fixture(ctx)
        ctx.fixture = describe()
        self.app_dir = ctx.cache_dir / "app"
        self.env = _env(ctx)


class _Compile(_Primed):
    """``reflex compile`` of the primed app, after an edit of ``edit``'s hot reload target when set.

    ``conclude`` restores the edited module, so the cached app stays the
    fixture its stamp describes.
    """

    timeout = QUICK_S
    edit: tuple[Path, str] | None = None
    restore: tuple[Path, bytes] | None = None
    marker: str | None = None

    def setup(self, ctx: Context) -> None:
        """Record the fixture and the collector and build the environment.

        Args:
            ctx: The benchmark context.
        """
        super().setup(ctx)
        _record_collector(ctx)

    def prepare(self, ctx: Context) -> None:
        """Give the edited hot reload target, if any, a new string.

        Args:
            ctx: The benchmark context.
        """
        if self.edit is not None:
            path, target = self.edit
            self.restore = (path, path.read_bytes())
            self.marker = bump_marker(path, target, next(_EDITS))

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
            timeout=self.timeout,
            **edited,
        )

    def conclude(self, ctx: Context) -> None:
        """Restore the edited module.

        Args:
            ctx: The benchmark context.
        """
        if self.restore is not None:
            self.restore[0].write_bytes(self.restore[1])


@_playground(id="lifecycle.compile.warm", suites=("pr", "daily"), estimate=1.3)
class CompileWarm(_Compile):
    """`reflex compile` of the primed playground, unchanged since the last compile."""


@_playground(id="lifecycle.compile.incremental", suites=("pr", "daily"), estimate=1.3)
class CompileIncremental(_Compile):
    """`reflex compile` of the primed playground after an edit of the leaf component."""

    def setup(self, ctx: Context) -> None:
        """Pick the leaf hot reload target of the playground.

        Args:
            ctx: The benchmark context.
        """
        super().setup(ctx)
        self.edit = (self.app_dir / "playground" / "components" / "marker.py", "leaf")


class _Export(_Compile):
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


@_playground(id="lifecycle.export.dev", estimate=7)
class ExportDev(_Export):
    """`reflex export --env dev` of the primed playground: frontend build and both zips."""

    mode = "dev"


@_playground(id="lifecycle.export.prod", estimate=7)
class ExportProd(_Export):
    """`reflex export --env prod` of the primed playground: frontend build and both zips."""

    mode = "prod"


class _Ready(_Primed):
    """``reflex run`` of the primed playground until it answers HTTP; conclude stops it.

    ``prepare`` plans the run, so ``conclude`` (also on a fresh thread after a
    timeout) always stops the app ``sample`` starts or was about to start.
    """

    mode: Mode = "dev"
    backend_only = False
    start_timeout = QUICK_S
    app: AppProcess

    def prepare(self, ctx: Context) -> None:
        """Plan the run.

        Args:
            ctx: The benchmark context.
        """
        self.app = AppProcess(
            ctx.subject.python,
            self.app_dir,
            mode=self.mode,
            reflex_version=ctx.subject.reflex_version,
            env=self.env,
            backend_only=self.backend_only,
            start_timeout=self.start_timeout,
        )

    def sample(self, ctx: Context) -> SampleResult:
        """Start the app and wait for tiers 1 (process-ready) and 2 (HTTP-ready).

        Args:
            ctx: The benchmark context.

        Returns:
            Seconds from the spawn to each tier, with the readiness as extra data.
        """
        readiness = self.app.start()
        http_ready = self.app.wait_http_ready(timeout=HTTP_S)
        return SampleResult(
            {"process_ready": readiness.process_ready, "http_ready": http_ready},
            extra={"readiness": dataclasses.asdict(readiness)},
        )

    def conclude(self, ctx: Context) -> None:
        """Kill the app's process tree, also after a failed or timed-out sample.

        Args:
            ctx: The benchmark context.
        """
        self.app.stop()


@_ready(id="lifecycle.run.dev.ready", estimate=4)
class RunDevReady(_Ready):
    """`reflex run --env dev` of the primed playground until the Vite dev server answers GET /."""


@_ready(id="lifecycle.run.prod.ready", timeout=SLOW_S + MARGIN_S, estimate=8)
class RunProdReady(_Ready):
    """`reflex run --env prod` of the primed playground: compile, frontend build and start."""

    mode = "prod"
    start_timeout = SLOW_S


@_ready(
    id="lifecycle.run.preview.ready",
    timeout=SLOW_S + MARGIN_S,
    estimate=6,
    min_version="0.9.8",
)
class RunPreviewReady(_Ready):
    """`reflex run --env preview` of the primed playground: an unminified build, then start."""

    mode = "preview"
    start_timeout = SLOW_S


@_ready(id="lifecycle.run.backend_only.ready", estimate=2)
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
            description="A fresh interpreter importing reflex and loading App and State.",
        )
    },
    warmup=1,
    timeout=QUICK_S + MARGIN_S,
    estimate=0.5,
)
class Import:
    """`python -c "import reflex as rx; rx.App; rx.State"` in a fresh interpreter: the framework's import graph."""

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
            prefix=("-c", IMPORT),
        ).check()
        return {"wall": result.wall_s}


class _Generated(_Compile):
    """A generated app of the tier's GenParams instead of the playground."""

    def fixture(
        self, ctx: Context
    ) -> tuple[Callable[[], FixtureDoc], Callable[[Path], object]]:
        """Choose the app.

        Args:
            ctx: The benchmark context.

        Returns:
            The generator's ``describe`` and ``generate`` for ``pages`` and the
            hidden parameters.
        """
        params = GenParams(**{
            f.name: ctx.params[f.name] for f in dataclasses.fields(GenParams)
        })
        return (
            functools.partial(generate.describe, params),
            functools.partial(generate.generate, params=params),
        )

    def setup(self, ctx: Context) -> None:
        """Give the largest tier the long compile timeout.

        Args:
            ctx: The benchmark context.
        """
        super().setup(ctx)
        self.timeout = SLOW_S if ctx.params["pages"] >= 1000 else QUICK_S


@_scale(id="lifecycle.scale.compile.warm")
class ScaleCompileWarm(_Generated):
    """`reflex compile` of a primed generated app, unchanged since the last compile."""


@_scale(id="lifecycle.scale.compile.incremental")
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
