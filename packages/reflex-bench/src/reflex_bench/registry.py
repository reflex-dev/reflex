"""The benchmark model: the ``@benchmark`` decorator, metrics, parameters and discovery.

A benchmark is a class with a ``sample(ctx)`` method and optional hooks, named
after hyperfine (``setup``/``prepare``/``conclude``/``cleanup``) plus asv's
``setup_cache``::

    @benchmark(
        id="selftest.sleep",
        suites=("selftest",),
        params={"ms": [10, 50]},
        metrics={"wall": Metric(unit="s", direction="lower")},
    )
    class Sleep:
        def sample(self, ctx):
            time.sleep(ctx.params["ms"] / 1000)

Each point of the parameter grid is one *instance*. :class:`Instance` binds one
to a :class:`~reflex_bench.context.Context` and exposes every hook as a
zero-argument method, so code other than the scheduler can drive a benchmark
hook by hook.
"""

from __future__ import annotations

import fnmatch
import hashlib
import importlib
import inspect
import itertools
import json
import math
import pkgutil
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypeVar

from packaging.version import InvalidVersion, Version

from reflex_bench import suites as suites_package
from reflex_bench.schema import (
    ASSUMPTIONS,
    DIRECTIONS,
    KINDS,
    Assume,
    Direction,
    Kind,
    format_name,
)
from reflex_bench.stats import unit_family

if TYPE_CHECKING:
    from reflex_bench.context import Context

SUITES = ("smoke", "pr", "daily", "all", "selftest")
SELFTEST_SUITE = "selftest"
# ``all`` is implicit: every benchmark except the self-tests.
_DECLARABLE_SUITES = tuple(suite for suite in SUITES if suite != "all")
_ID_PATTERN = re.compile(r"[a-z0-9_]+(?:\.[a-z0-9_]+)*")
_PARAM_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

_T = TypeVar("_T", bound=type)


@dataclass(frozen=True)
class Metric:
    """A quantity a benchmark measures.

    Attributes:
        unit: The SI base unit of stored values: ``s``, ``B``, ``ev/s``, ``1`` for
            counts. Display scaling (ms, MB) happens only when printing.
        direction: Which way is better, ``lower`` or ``higher``.
        assume: ``nothing`` (statistics apply) or ``exact`` for deterministic
            values: one run is enough and any variance is reported.
        description: A human-readable description.
    """

    unit: str
    direction: Direction
    assume: Assume = "nothing"
    description: str = ""

    def __post_init__(self) -> None:
        """Validate the declaration.

        Raises:
            ValueError: On an empty unit or an unknown direction or assumption.
        """
        if not self.unit:
            msg = "Metric.unit must not be empty"
            raise ValueError(msg)
        if self.direction not in DIRECTIONS:
            msg = (
                f"Metric.direction must be one of {DIRECTIONS}, got {self.direction!r}"
            )
            raise ValueError(msg)
        if self.assume not in ASSUMPTIONS:
            msg = f"Metric.assume must be one of {ASSUMPTIONS}, got {self.assume!r}"
            raise ValueError(msg)

    @property
    def family(self) -> str:
        """The unit family whose geomean this metric joins.

        Returns:
            ``time``, ``bytes``, ``rate``, ``count`` or the unit itself.
        """
        return unit_family(self.unit)


@dataclass(frozen=True)
class SampleResult:
    """What ``sample()`` may return: metric values plus per-sample extra data.

    Attributes:
        values: Metric values in SI base units, keyed by declared metric name.
        extra: JSON-serializable data stored with the sample (e.g. compile phases).
    """

    values: Mapping[str, float]
    extra: dict[str, Any] | None = None


@dataclass(frozen=True)
class ParamSet:
    """One point of a benchmark's parameter grid.

    Attributes:
        params: Visible parameters: part of the instance name and the series key.
        hidden: Hidden parameters: passed to hooks and stored, but not part of the
            name or the series key (e.g. the self-test ``shift``).
    """

    params: dict[str, Any]
    hidden: dict[str, Any] = field(default_factory=dict)

    @property
    def merged(self) -> dict[str, Any]:
        """All parameters, as hooks see them in ``ctx.params``.

        Returns:
            Visible and hidden parameters together.
        """
        return {**self.params, **self.hidden}


def coerce_param(raw: object, declared: Sequence[Any]) -> Any:
    """Convert a ``--param`` value to the type of a parameter's declared values.

    Args:
        raw: The override; strings come from the command line.
        declared: The parameter's declared values (or its default, for hidden ones).

    Returns:
        The matching declared value if the text matches one, else the JSON value
        of the text (``10`` becomes an int, ``1.2`` a float), else the text.
    """
    if not isinstance(raw, str):
        return raw
    for value in declared:
        if str(value) == raw:
            return value
    try:
        value = json.loads(raw)
    except ValueError:
        return raw
    # json.loads accepts NaN and Infinity, which a result document cannot store.
    return value if _is_json(value) else raw


def _is_json(value: object) -> bool:
    """Check that a parameter value can be stored in a result document.

    Args:
        value: The value.

    Returns:
        Whether ``json.dumps`` accepts it without NaN or infinity.
    """
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError):
        return False
    return True


def _source_version(target: type) -> str:
    """Hash a benchmark class's source, decorator included.

    Args:
        target: The benchmark class.

    Returns:
        ``sha256:<hex>``; the qualified name is hashed when the source is not
        available.
    """
    try:
        source = inspect.getsource(target)
    except (OSError, TypeError):
        source = f"{target.__module__}.{target.__qualname__}"
    return "sha256:" + hashlib.sha256(source.encode()).hexdigest()


@dataclass(frozen=True, eq=False)
class Benchmark:
    """A registered benchmark definition.

    Attributes:
        id: The dotted benchmark id, e.g. ``lifecycle.compile.warm``.
        cls: The benchmark class; instantiated without arguments per instance.
        suites: The named selections the benchmark belongs to.
        kind: What the benchmark measures: time, startup, rate, latency, peakmem
            or track.
        params: Visible parameter grid; the cartesian product gives the instances.
        hidden_params: Hidden parameters and their defaults.
        metrics: The declared metrics.
        warmup: Untimed runs before the timed ones.
        timeout: Seconds allowed for each prepare, sample and conclude call.
        setup_timeout: Seconds allowed for setup_cache, setup and cleanup.
        estimate: Rough seconds per sample, for ``list``.
        min_version: The oldest reflex version the benchmark supports.
        version: Hash of the class source; results of different versions are
            never compared.
        description: The first line of the class docstring.
    """

    id: str
    cls: type
    suites: tuple[str, ...]
    kind: Kind
    params: dict[str, tuple[Any, ...]]
    hidden_params: dict[str, Any]
    metrics: dict[str, Metric]
    warmup: int
    timeout: float
    setup_timeout: float
    estimate: float
    min_version: str | None
    version: str
    description: str

    @classmethod
    def define(
        cls,
        target: type,
        *,
        id: str,
        metrics: Mapping[str, Metric],
        suites: Sequence[str] = (),
        kind: Kind = "time",
        params: Mapping[str, Sequence[Any]] | None = None,
        hidden_params: Mapping[str, Any] | None = None,
        warmup: int = 0,
        timeout: float = 60.0,
        setup_timeout: float = 600.0,
        estimate: float = 1.0,
        min_version: str | None = None,
    ) -> Benchmark:
        """Validate a benchmark declaration without registering it.

        Args:
            target: The benchmark class.
            id: The dotted benchmark id.
            metrics: The declared metrics.
            suites: The named selections the benchmark belongs to.
            kind: What the benchmark measures.
            params: Parameter name to the values to run.
            hidden_params: Hidden parameter name to its default.
            warmup: Untimed runs before the timed ones.
            timeout: Seconds allowed for each prepare, sample and conclude call.
            setup_timeout: Seconds allowed for setup_cache, setup and cleanup.
            estimate: Rough seconds per sample.
            min_version: The oldest supported reflex version.

        Returns:
            The benchmark definition.

        Raises:
            ValueError: On an invalid declaration.
            TypeError: When the class has no ``sample`` method.
        """
        problems: list[str] = []
        if not _ID_PATTERN.fullmatch(id):
            problems.append(f"id {id!r} must be dotted lowercase words")
        if kind not in KINDS:
            problems.append(f"kind must be one of {KINDS}, got {kind!r}")
        if not metrics:
            problems.append("declare at least one metric")
        grid = {name: tuple(values) for name, values in (params or {}).items()}
        hidden = dict(hidden_params or {})
        problems.extend(
            f"parameter name {name!r} is not an identifier"
            for name in (*grid, *hidden)
            if not _PARAM_PATTERN.fullmatch(name)
        )
        problems.extend(
            f"parameter {name!r} has no values"
            for name, values in grid.items()
            if not values
        )
        problems.extend(
            f"parameter {name!r} value {value!r} is not JSON serializable"
            for name, values in (*grid.items(), *((n, (v,)) for n, v in hidden.items()))
            for value in values
            if not _is_json(value)
        )
        if overlap := grid.keys() & hidden.keys():
            problems.append(f"parameters {sorted(overlap)} are both visible and hidden")
        if unknown := [s for s in suites if s not in _DECLARABLE_SUITES]:
            problems.append(
                f"unknown suites {unknown}; choose from {_DECLARABLE_SUITES}"
            )
        if warmup < 0 or timeout <= 0 or setup_timeout <= 0 or estimate < 0:
            problems.append("warmup and estimate must be >= 0, timeouts > 0")
        if min_version is not None:
            try:
                Version(min_version)
            except InvalidVersion:
                problems.append(f"min_version {min_version!r} is not a version")
        if problems:
            msg = f"invalid benchmark {target.__qualname__}: " + "; ".join(problems)
            raise ValueError(msg)
        if not callable(getattr(target, "sample", None)):
            msg = f"benchmark {target.__qualname__} must define sample(self, ctx)"
            raise TypeError(msg)
        return cls(
            id=id,
            cls=target,
            suites=tuple(suites),
            kind=kind,
            params=grid,
            hidden_params=hidden,
            metrics=dict(metrics),
            warmup=warmup,
            timeout=float(timeout),
            setup_timeout=float(setup_timeout),
            estimate=float(estimate),
            min_version=min_version,
            version=_source_version(target),
            description=(inspect.getdoc(target) or "").partition("\n")[0],
        )

    @property
    def exact(self) -> bool:
        """Whether every metric is deterministic, so one run is enough.

        Returns:
            True when all metrics assume ``exact``.
        """
        return all(metric.assume == "exact" for metric in self.metrics.values())

    @property
    def param_names(self) -> set[str]:
        """Every parameter ``--param`` may set.

        Returns:
            Visible and hidden parameter names.
        """
        return {*self.params, *self.hidden_params}

    def expand(self, overrides: Mapping[str, object] | None = None) -> list[ParamSet]:
        """Expand the parameter grid into instances.

        Args:
            overrides: Parameter values that replace a parameter's declared values
                (restricting the grid to one value) or a hidden parameter's default.
                Keys this benchmark does not declare are ignored.

        Returns:
            One parameter set per point of the cartesian product, in declaration
            order.
        """
        overrides = overrides or {}
        axes = [
            (coerce_param(overrides[name], values),) if name in overrides else values
            for name, values in self.params.items()
        ]
        hidden = {
            name: coerce_param(overrides[name], (default,))
            if name in overrides
            else default
            for name, default in self.hidden_params.items()
        }
        return [
            ParamSet(dict(zip(self.params, point, strict=True)), dict(hidden))
            for point in itertools.product(*axes)
        ]

    def normalize(self, raw: object, wall_s: float | None = None) -> SampleResult:
        """Check what ``sample()`` returned against the declared metrics.

        Args:
            raw: ``None``, a mapping of metric values or a :class:`SampleResult`.
            wall_s: The measured duration of the call, which fills a declared
                ``wall`` metric that ``sample()`` did not return.

        Returns:
            A result with a finite float for every declared metric.

        Raises:
            TypeError: On an unsupported return type or non-dict extra data.
            ValueError: On an undeclared or missing metric, a non-finite value or
                extra data that is not JSON-serializable.
        """
        if raw is None:
            values: Mapping[str, object] = {}
            extra = None
        elif isinstance(raw, SampleResult):
            values, extra = raw.values, raw.extra
        elif isinstance(raw, Mapping):
            values, extra = raw, None
        else:
            msg = (
                f"{self.id}: sample() must return None, a dict of metric values or a"
                f" SampleResult, not {type(raw).__name__}"
            )
            raise TypeError(msg)
        if unknown := values.keys() - self.metrics.keys():
            msg = (
                f"{self.id}: sample() returned undeclared metric(s)"
                f" {', '.join(sorted(map(str, unknown)))}; declared: {', '.join(self.metrics)}"
            )
            raise ValueError(msg)
        checked: dict[str, float] = {}
        for name in self.metrics:
            if name in values:
                value = values[name]
            elif name == "wall" and wall_s is not None:
                value = wall_s
            else:
                msg = f"{self.id}: sample() did not return metric {name!r}"
                raise ValueError(msg)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                msg = (
                    f"{self.id}: metric {name!r} must be a finite number, got {value!r}"
                )
                raise ValueError(msg)
            checked[name] = float(value)
        if extra is not None:
            if not isinstance(extra, dict):
                msg = f"{self.id}: SampleResult.extra must be a dict or None"
                raise TypeError(msg)
            try:
                json.dumps(extra, allow_nan=False)
            except (TypeError, ValueError) as exc:
                msg = f"{self.id}: SampleResult.extra must be JSON-serializable: {exc}"
                raise ValueError(msg) from exc
        return SampleResult(checked, extra)


class Instance:
    """A benchmark bound to one parameter set and a context.

    Every hook is a zero-argument method and all state lives on the benchmark
    object or the context, so any caller can drive the hooks one at a time, e.g.
    ``benchmark.pedantic(inst.sample, setup=inst.prepare, teardown=inst.conclude)``.
    """

    def __init__(self, benchmark: Benchmark, params: ParamSet, ctx: Context) -> None:
        """Instantiate the benchmark class.

        Args:
            benchmark: The benchmark definition.
            params: The parameter set; ``ctx.params`` should be ``params.merged``.
            ctx: The context passed to every hook.
        """
        self.benchmark = benchmark
        self.params = params
        self.ctx = ctx
        self.obj = benchmark.cls()

    @property
    def name(self) -> str:
        """The instance name.

        Returns:
            ``id`` or ``id[key=value,...]``.
        """
        return format_name(self.benchmark.id, self.params.params)

    def _call(self, hook: str) -> None:
        """Call an optional hook if the benchmark defines it.

        Args:
            hook: The hook name.
        """
        method = getattr(self.obj, hook, None)
        if method is not None:
            method(self.ctx)

    def setup_cache(self) -> None:
        """Run ``setup_cache``: once per subject and parameter set."""
        self._call("setup_cache")

    def setup(self) -> None:
        """Run ``setup``: once per instance run."""
        self._call("setup")

    def prepare(self) -> None:
        """Run ``prepare``: before each sample, untimed."""
        self._call("prepare")

    def sample(self) -> object:
        """Take one sample.

        Returns:
            What the benchmark's ``sample`` returned; see :meth:`Benchmark.normalize`.
        """
        return self.obj.sample(self.ctx)

    def conclude(self) -> None:
        """Run ``conclude``: after each sample, untimed."""
        self._call("conclude")

    def cleanup(self) -> None:
        """Run ``cleanup``: once after the last sample."""
        self._call("cleanup")


REGISTRY: dict[str, Benchmark] = {}


def _qualified(target: type) -> str:
    """Name a class unambiguously.

    Args:
        target: The class.

    Returns:
        ``module.qualname``.
    """
    return f"{target.__module__}.{target.__qualname__}"


def register(bench: Benchmark) -> None:
    """Add a benchmark to the registry.

    Re-registering the same class (e.g. after a module reload) replaces it.

    Args:
        bench: The benchmark definition.

    Raises:
        ValueError: When another class already uses the id.
    """
    existing = REGISTRY.get(bench.id)
    if existing is not None and _qualified(existing.cls) != _qualified(bench.cls):
        msg = (
            f"duplicate benchmark id {bench.id!r}: {_qualified(existing.cls)}"
            f" and {_qualified(bench.cls)}"
        )
        raise ValueError(msg)
    REGISTRY[bench.id] = bench


def benchmark(
    *,
    id: str,
    metrics: Mapping[str, Metric],
    suites: Sequence[str] = (),
    kind: Kind = "time",
    params: Mapping[str, Sequence[Any]] | None = None,
    hidden_params: Mapping[str, Any] | None = None,
    warmup: int = 0,
    timeout: float = 60.0,
    setup_timeout: float = 600.0,
    estimate: float = 1.0,
    min_version: str | None = None,
) -> Callable[[_T], _T]:
    """Declare and register a benchmark class.

    Args:
        id: The dotted benchmark id, unique across all suites.
        metrics: The declared metrics; ``sample()`` must return exactly these (a
            declared ``wall`` metric is filled with the measured duration).
        suites: The named selections the benchmark belongs to.
        kind: What the benchmark measures: time, startup, rate, latency, peakmem
            or track.
        params: Parameter name to values; the cartesian product gives instances.
        hidden_params: Parameter name to default for parameters that are passed to
            hooks but are not part of the instance name or the series key.
        warmup: Untimed runs before the timed ones.
        timeout: Seconds allowed for each prepare, sample and conclude call.
        setup_timeout: Seconds allowed for setup_cache, setup and cleanup.
        estimate: Rough seconds per sample, shown by ``list``.
        min_version: The oldest reflex version the benchmark supports; older
            subjects report ``unsupported``.

    Returns:
        A class decorator that registers the class and returns it unchanged.
    """

    def decorate(target: _T) -> _T:
        register(
            Benchmark.define(
                target,
                id=id,
                metrics=metrics,
                suites=suites,
                kind=kind,
                params=params,
                hidden_params=hidden_params,
                warmup=warmup,
                timeout=timeout,
                setup_timeout=setup_timeout,
                estimate=estimate,
                min_version=min_version,
            )
        )
        return target

    return decorate


def discover() -> dict[str, Benchmark]:
    """Import every module in :mod:`reflex_bench.suites` and return the registry.

    Returns:
        The registered benchmarks, sorted by id.
    """
    for module in pkgutil.iter_modules(suites_package.__path__):
        importlib.import_module(f"{suites_package.__name__}.{module.name}")
    return dict(sorted(REGISTRY.items()))


def select(
    benchmarks: Iterable[Benchmark],
    filters: Sequence[str] = (),
    suite: str | None = None,
) -> list[Benchmark]:
    """Choose benchmarks by suite and id globs.

    A benchmark is chosen when it matches any filter (or there are none) and is in
    the suite (if given). ``all`` means every benchmark except the self-tests.
    Self-tests are also left out when no suite is given, unless a filter starting
    with ``selftest`` names them.

    Args:
        benchmarks: The candidates.
        filters: Globs on the benchmark id, e.g. ``lifecycle.*``.
        suite: A named selection.

    Returns:
        The chosen benchmarks, sorted by id.
    """
    chosen: list[Benchmark] = []
    for bench in sorted(benchmarks, key=lambda b: b.id):
        selftest = SELFTEST_SUITE in bench.suites
        if suite == "all":
            in_suite = not selftest
        else:
            in_suite = suite is None or suite in bench.suites
        patterns = filters
        if suite is None and selftest:
            patterns = [f for f in filters if f.startswith(SELFTEST_SUITE)]
            if not patterns:
                continue
        if in_suite and (
            not patterns or any(fnmatch.fnmatchcase(bench.id, f) for f in patterns)
        ):
            chosen.append(bench)
    return chosen


def parse_overrides(pairs: Sequence[str]) -> dict[str, str]:
    """Parse ``--param KEY=VALUE`` options.

    Args:
        pairs: The raw options.

    Returns:
        Parameter name to raw value; later options win.

    Raises:
        ValueError: On an option without ``=`` or a key.
    """
    overrides: dict[str, str] = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep or not key.strip():
            msg = f"--param expects KEY=VALUE, got {pair!r}"
            raise ValueError(msg)
        overrides[key.strip()] = value
    return overrides
