"""Tests for reflex_bench.registry."""

from __future__ import annotations

import pytest
from reflex_bench import registry
from reflex_bench.registry import Benchmark, Metric, ParamSet, SampleResult

from .factories import WALL, make_context


class _Sampler:
    """A benchmark class with only a sample method."""

    def sample(self, ctx):
        """Take no measurement.

        Args:
            ctx: The benchmark context.
        """


@pytest.fixture
def fresh_registry(monkeypatch: pytest.MonkeyPatch) -> dict[str, Benchmark]:
    table: dict[str, Benchmark] = {}
    monkeypatch.setattr(registry, "REGISTRY", table)
    return table


def test_decorator_registers_and_returns_the_class(fresh_registry):
    @registry.benchmark(id="t.one", metrics={"wall": WALL}, params={"n": [1, 2]})
    class One:
        """First line.

        More text.
        """

        def sample(self, ctx):
            """Sample.

            Args:
                ctx: The benchmark context.
            """

    bench = fresh_registry["t.one"]
    assert bench.cls is One
    assert bench.description == "First line."
    assert bench.params == {"n": (1, 2)}
    assert bench.version.startswith("sha256:")
    assert len(bench.version) == len("sha256:") + 64


class _Doubler:
    """A benchmark base whose sample differs from _Sampler's."""

    def sample(self, ctx):
        """Take a different measurement.

        Args:
            ctx: The benchmark context.
        """


def _leaf(base: type) -> type:
    """Subclass base without overriding anything.

    Args:
        base: The class that holds the measurement hooks.

    Returns:
        A leaf class whose own source is the same for every base.
    """

    class Leaf(base):
        """Inherit the measurement."""

    return Leaf


def test_version_covers_inherited_hooks():
    def version(base: type) -> str:
        return Benchmark.define(
            _leaf(base), id="t.leaf", metrics={"wall": WALL}
        ).version

    assert version(_Sampler) == version(_Sampler)
    assert version(_Sampler) != version(_Doubler)


def test_duplicate_ids_are_an_error(fresh_registry):
    registry.register(Benchmark.define(_Sampler, id="t.dup", metrics={"wall": WALL}))
    # The same class may re-register, e.g. after a module reload.
    registry.register(Benchmark.define(_Sampler, id="t.dup", metrics={"wall": WALL}))

    class Other(_Sampler):
        """Another class."""

    with pytest.raises(ValueError, match=r"duplicate benchmark id 't\.dup'"):
        registry.register(Benchmark.define(Other, id="t.dup", metrics={"wall": WALL}))


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"id": "Bad Id"}, "must be dotted lowercase words"),
        ({"kind": "speed"}, "kind must be one of"),
        ({"metrics": {}}, "declare at least one metric"),
        ({"params": {"n": []}}, "parameter 'n' has no values"),
        ({"params": {"n": [1]}, "hidden_params": {"n": 2}}, "both visible and hidden"),
        ({"params": {"1n": [1]}}, "is not an identifier"),
        ({"params": {"p": [object()]}}, "parameter 'p' value .* is not JSON"),
        ({"hidden_params": {"h": float("nan")}}, "parameter 'h' value nan is not JSON"),
        ({"suites": ("nightly",)}, "unknown suites"),
        ({"suites": ("all",)}, "unknown suites"),
        ({"timeout": 0}, "timeouts > 0"),
        ({"min_version": "not a version"}, "is not a version"),
        (
            {"params": {"n": [1, 2]}, "suite_params": {"smoke": {"n": [1]}}},
            "suite_params name suite 'smoke', which the benchmark is not in",
        ),
        (
            {
                "suites": ("smoke",),
                "params": {"n": [1, 2]},
                "suite_params": {"smoke": {"m": [1]}},
            },
            "suite_params of 'smoke' name undeclared parameter 'm'",
        ),
        (
            {
                "suites": ("smoke",),
                "params": {"n": [1, 2]},
                "suite_params": {"smoke": {"n": []}},
            },
            "suite_params of 'smoke': parameter 'n' has no values",
        ),
    ],
)
def test_invalid_declarations(kwargs, message):
    arguments = {"id": "t.x", "metrics": {"wall": WALL}, **kwargs}
    with pytest.raises(ValueError, match=message):
        Benchmark.define(_Sampler, **arguments)


def test_class_without_sample_is_rejected():
    class NoSample:
        """No sample method."""

    with pytest.raises(TypeError, match=r"must define sample\(self, ctx\)"):
        Benchmark.define(NoSample, id="t.x", metrics={"wall": WALL})


def test_metric_validation():
    with pytest.raises(ValueError, match="direction"):
        Metric(unit="s", direction="up")  # pyright: ignore[reportArgumentType]
    with pytest.raises(ValueError, match="assume"):
        Metric(unit="s", direction="lower", assume="maybe")  # pyright: ignore[reportArgumentType]
    with pytest.raises(ValueError, match="unit"):
        Metric(unit="", direction="lower")
    assert Metric(unit="ev/s", direction="higher").family == "rate"


def test_expand_is_a_cartesian_product_in_declaration_order():
    bench = Benchmark.define(
        _Sampler,
        id="t.grid",
        metrics={"wall": WALL},
        params={"pages": [10, 100], "env": ["dev", "prod"]},
        hidden_params={"shift": 1.0},
    )
    expanded = bench.expand()
    assert [p.params for p in expanded] == [
        {"pages": 10, "env": "dev"},
        {"pages": 10, "env": "prod"},
        {"pages": 100, "env": "dev"},
        {"pages": 100, "env": "prod"},
    ]
    assert all(p.hidden == {"shift": 1.0} for p in expanded)
    assert expanded[0].merged == {"pages": 10, "env": "dev", "shift": 1.0}


def test_overrides_restrict_or_replace_values_and_keep_types():
    bench = Benchmark.define(
        _Sampler,
        id="t.grid",
        metrics={"wall": WALL},
        params={"pages": [10, 100], "env": ["dev", "prod"]},
        hidden_params={"shift": 1.0},
    )
    restricted = bench.expand({"pages": "100", "shift": "1.2", "unrelated": "x"})
    assert [p.params for p in restricted] == [
        {"pages": 100, "env": "dev"},
        {"pages": 100, "env": "prod"},
    ]
    assert restricted[0].hidden == {"shift": 1.2}
    assert bench.expand({"pages": "250"})[0].params["pages"] == 250
    assert bench.expand({"env": "staging"})[0].params["env"] == "staging"
    assert bench.param_names == {"pages", "env", "shift"}


def test_suite_params_narrow_the_grid_of_one_suite():
    bench = Benchmark.define(
        _Sampler,
        id="t.grid",
        metrics={"wall": WALL},
        suites=("smoke", "daily"),
        params={"sessions": [1, 10, 50], "rate": ["auto"]},
        suite_params={"smoke": {"sessions": [10], "rate": [50]}},
    )
    assert [p.params for p in bench.expand(suite="smoke")] == [
        {"sessions": 10, "rate": 50}
    ]
    assert len(bench.expand(suite="daily")) == 3
    assert len(bench.expand()) == 3
    # --param still wins.
    assert [p.params for p in bench.expand({"sessions": "50"}, suite="smoke")] == [
        {"sessions": 50, "rate": 50}
    ]


def test_coerce_param():
    assert registry.coerce_param("10", (10, 50)) == 10
    assert registry.coerce_param("1.5", (1.0,)) == pytest.approx(1.5)
    assert registry.coerce_param("true", (False,)) is True
    assert registry.coerce_param("prod", ("dev",)) == "prod"
    assert registry.coerce_param(7, (1,)) == 7
    assert registry.coerce_param("NaN", (1.0,)) == "NaN"


def test_parse_overrides():
    assert registry.parse_overrides(["a=1", "b = x", "a=2", "c="]) == {
        "a": "2",
        "b": " x",
        "c": "",
    }
    with pytest.raises(ValueError, match="KEY=VALUE"):
        registry.parse_overrides(["novalue"])


@pytest.fixture
def two_metrics() -> Benchmark:
    return Benchmark.define(
        _Sampler,
        id="t.m",
        metrics={
            "wall": WALL,
            "bytes": Metric(unit="B", direction="lower", assume="exact"),
        },
    )


def test_normalize_fills_wall_from_the_measurement(two_metrics):
    result = two_metrics.normalize({"bytes": 10}, wall_s=0.25)
    assert result == SampleResult({"wall": 0.25, "bytes": 10.0})


def test_normalize_prefers_a_returned_wall_value(two_metrics):
    result = two_metrics.normalize(
        SampleResult({"wall": 1, "bytes": 2}, {"phase": 1}), 9.0
    )
    assert result.values == {"wall": 1.0, "bytes": 2.0}
    assert result.extra == {"phase": 1}


def test_normalize_rejects_undeclared_metrics(two_metrics):
    with pytest.raises(
        ValueError, match=r"undeclared metric\(s\) byts; declared: wall, bytes"
    ):
        two_metrics.normalize({"byts": 1, "bytes": 1}, 0.1)


def test_normalize_requires_every_declared_metric(two_metrics):
    with pytest.raises(ValueError, match="did not return metric 'bytes'"):
        two_metrics.normalize(None, 0.1)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, "1"])
def test_normalize_rejects_non_finite_values(two_metrics, value):
    with pytest.raises(ValueError, match="must be a finite number"):
        two_metrics.normalize({"bytes": value}, 0.1)


def test_normalize_rejects_bad_return_types_and_extra(two_metrics):
    with pytest.raises(TypeError, match="must return None, a dict"):
        two_metrics.normalize([1, 2], 0.1)
    with pytest.raises(TypeError, match="extra must be a dict"):
        two_metrics.normalize(SampleResult({"bytes": 1}, [1]), 0.1)  # pyright: ignore[reportArgumentType]
    with pytest.raises(ValueError, match="JSON-serializable"):
        two_metrics.normalize(SampleResult({"bytes": 1}, {"x": object()}), 0.1)


def test_exact_benchmarks(two_metrics):
    assert not two_metrics.exact
    exact = Benchmark.define(
        _Sampler,
        id="t.e",
        metrics={"bytes": Metric(unit="B", direction="lower", assume="exact")},
    )
    assert exact.exact


def test_discover_finds_the_self_tests():
    found = registry.discover()
    assert {
        "selftest.sleep",
        "selftest.noise",
        "selftest.exact",
        "selftest.fail",
        "selftest.timeout",
    } <= found.keys()
    assert list(found) == sorted(found)


def _ids(benchmarks) -> list[str]:
    return [b.id for b in benchmarks]


@pytest.fixture
def catalog() -> list[Benchmark]:
    def define(bench_id: str, suites: tuple[str, ...]) -> Benchmark:
        return Benchmark.define(
            _Sampler, id=bench_id, metrics={"wall": WALL}, suites=suites
        )

    return [
        define("lifecycle.compile.warm", ("pr", "daily")),
        define("lifecycle.compile.cold", ("daily",)),
        define("events.throughput", ("smoke", "pr")),
        define("selftest.sleep", ("selftest",)),
        define("selftest.fail", ("selftest",)),
    ]


def test_select_hides_self_tests_by_default(catalog):
    assert _ids(registry.select(catalog)) == [
        "events.throughput",
        "lifecycle.compile.cold",
        "lifecycle.compile.warm",
    ]
    assert _ids(registry.select(catalog, ["*"])) == _ids(registry.select(catalog))
    assert _ids(registry.select(catalog, suite="all")) == _ids(registry.select(catalog))


def test_select_by_suite_and_glob(catalog):
    assert _ids(registry.select(catalog, suite="pr")) == [
        "events.throughput",
        "lifecycle.compile.warm",
    ]
    assert _ids(registry.select(catalog, ["lifecycle.*"])) == [
        "lifecycle.compile.cold",
        "lifecycle.compile.warm",
    ]
    assert _ids(registry.select(catalog, ["*.warm"], suite="daily")) == [
        "lifecycle.compile.warm"
    ]
    assert _ids(registry.select(catalog, suite="selftest")) == [
        "selftest.fail",
        "selftest.sleep",
    ]


def test_select_self_tests_by_name(catalog):
    assert _ids(registry.select(catalog, ["selftest.sleep"])) == ["selftest.sleep"]
    assert _ids(registry.select(catalog, ["selftest.*", "events.*"])) == [
        "events.throughput",
        "selftest.fail",
        "selftest.sleep",
    ]


def test_instance_hooks_are_callable_one_by_one(tmp_path):
    calls: list[str] = []

    class Hooked:
        """Records its hook calls."""

        def setup(self, ctx):
            """Record.

            Args:
                ctx: The benchmark context.
            """
            calls.append(f"setup:{ctx.params['n']}")

        def sample(self, ctx):
            """Record.

            Args:
                ctx: The benchmark context.

            Returns:
                A metric value.
            """
            calls.append("sample")
            return {"wall": 1.0}

    bench = Benchmark.define(
        Hooked, id="t.h", metrics={"wall": WALL}, params={"n": [3]}
    )
    params = ParamSet({"n": 3})
    instance = registry.Instance(bench, params, make_context(tmp_path, params.merged))
    assert instance.name == "t.h[n=3]"
    instance.setup_cache()
    instance.setup()
    instance.prepare()
    assert instance.sample() == {"wall": 1.0}
    instance.conclude()
    instance.cleanup()
    assert calls == ["setup:3", "sample"]
