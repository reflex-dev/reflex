"""Single-page microbenchmark for the run-rust pipeline.

Builds **one** feature-rich page (state, vars, foreach, cond, match,
event handlers, markdown — all the stuff that creates memo candidates +
add_imports overrides), then runs the actual compile_pages flow with
per-phase timers labeled Python / Rust / Hybrid so we know exactly
which work is Python-bound and which is in the Rust extension.

Each phase is timed inside an instrumented copy of
``reflex.compiler.rust_pipeline.compile_pages``'s page loop — same code
path the CLI runs, just with ``perf_counter_ns`` around each step.

Usage:
    uv run python scripts/benchmark_single_page.py [runs]

Default: 10 runs. First run is treated as a warmup and excluded from
the aggregate so the per-component ``_imports_cache`` doesn't make
subsequent runs look artificially cheap.
"""

from __future__ import annotations

import os
import statistics
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path


def _ns() -> int:
    return time.perf_counter_ns()


def _ms(ns: int | float) -> float:
    return ns / 1_000_000


# ---------------------------------------------------------------------------
# Synthetic page
# ---------------------------------------------------------------------------


def _build_app(scale: int = 1):
    """One page exercising the surfaces compile_pages touches.

    Args:
        scale: how many "section" blocks to repeat. ``scale=1`` is the
            ~47-node baseline; each extra unit adds ~80 nodes.

    Returns:
        A loaded ``rx.App`` with a single ``/bench`` route registered.
    """
    import reflex as rx

    class BenchState(rx.State):
        items: list[str] = [f"item-{i}" for i in range(20)]
        counter: int = 0
        current_key: str = "k1"

        @rx.event
        def increment(self) -> None:
            self.counter += 1

        @rx.event
        def zero_counter(self) -> None:
            self.counter = 0

    def row(item: rx.Var) -> rx.Component:
        return rx.hstack(
            rx.text(item),
            rx.button("inc", on_click=BenchState.increment),
            rx.button("reset", on_click=BenchState.zero_counter),
        )

    def section() -> rx.Component:
        return rx.vstack(
            rx.heading("Microbench page", size="3"),
            rx.text(f"counter: {BenchState.counter}"),
            rx.markdown(
                "# header\n\nSome **markdown** with `code` and a [link](https://x)."
            ),
            rx.cond(
                BenchState.counter > 0,
                rx.box(rx.text("positive"), rx.button("more")),
                rx.box(rx.text("non-positive"), rx.button("kick")),
            ),
            rx.match(
                BenchState.current_key,
                ("k1", rx.text("key 1 active")),
                ("k2", rx.text("key 2 active")),
                rx.text("default"),
            ),
            rx.foreach(BenchState.items, row),
            rx.hstack(
                rx.button("global inc", on_click=BenchState.increment),
                rx.button("global reset", on_click=BenchState.zero_counter),
            ),
        )

    def page() -> rx.Component:
        return rx.vstack(*[section() for _ in range(scale)])

    app = rx.App()
    app.add_page(page, route="/bench")
    return app


# ---------------------------------------------------------------------------
# Phase timer
# ---------------------------------------------------------------------------


class PhaseTimer:
    """Accumulates per-phase nanosecond durations across runs.

    Phases are tagged ``python``, ``rust``, or ``hybrid`` (Rust walk
    that calls back into Python). The summary makes the runtime split
    explicit.
    """

    KIND_ORDER = {"python": 0, "hybrid": 1, "rust": 2}

    def __init__(self) -> None:
        self.samples: dict[str, list[int]] = {}
        self.kinds: dict[str, str] = {}
        self.order: list[str] = []

    @contextmanager
    def measure(self, name: str, kind: str = "python"):
        if name not in self.kinds:
            self.kinds[name] = kind
            self.order.append(name)
        t0 = _ns()
        try:
            yield
        finally:
            self.samples.setdefault(name, []).append(_ns() - t0)

    def trim_warmup(self) -> None:
        """Discard the first sample of every phase (the cold-cache run)."""
        for name in self.samples:
            if len(self.samples[name]) > 1:
                self.samples[name] = self.samples[name][1:]

    def report(self, runs: int) -> None:
        per_run_medians: list[tuple[str, float, str]] = []
        kind_run_totals = {"python": 0.0, "hybrid": 0.0, "rust": 0.0}

        header = (
            f"{'phase':<46}{'kind':<8}"
            f"{'median':>9}{'mean':>9}{'p95':>9}{'min':>9}{'max':>9}"
        )
        print(header)
        print(f"{'':<46}{'':<8}{'(ms)':>9}{'(ms)':>9}{'(ms)':>9}{'(ms)':>9}{'(ms)':>9}")
        print("-" * len(header))

        for name in self.order:
            samples = [s / 1_000_000 for s in self.samples[name]]
            median = statistics.median(samples)
            mean = statistics.mean(samples)
            p95 = _p95(samples)
            mn = min(samples)
            mx = max(samples)
            kind = self.kinds[name]
            per_run_medians.append((name, median, kind))
            kind_run_totals[kind] += median
            print(
                f"{name:<46}{kind:<8}"
                f"{median:>9.3f}{mean:>9.3f}{p95:>9.3f}{mn:>9.3f}{mx:>9.3f}"
            )

        per_run_median_total = sum(m for _, m, _ in per_run_medians)
        print("-" * len(header))
        print(f"{'Per-run median total:':<54}{per_run_median_total:>9.3f}  ms")
        print()
        print("Breakdown by where the work actually runs (median per run):")
        for kind in ("python", "hybrid", "rust"):
            t = kind_run_totals[kind]
            pct = (t / per_run_median_total * 100) if per_run_median_total else 0
            label = {
                "python": "Python only",
                "hybrid": "Rust + PyO3 callbacks",
                "rust":   "pure Rust (no callbacks)",
            }[kind]
            print(f"  {label:<28}{t:>8.2f} ms  ({pct:5.1f}%)")
        print()
        print(f"Runs aggregated: {runs} (1 warmup discarded)")


def _p95(samples: list[float]) -> float:
    if not samples:
        return 0.0
    s = sorted(samples)
    return s[int(0.95 * (len(s) - 1))]


# ---------------------------------------------------------------------------
# Instrumented compile loop
# ---------------------------------------------------------------------------


def _instrumented_compile_pages(app, sess, timer: PhaseTimer, web_dir: Path) -> None:
    """Mirror of ``rust_pipeline.compile_pages`` with per-phase timers.

    Skips the post-loop static-artifact emission (``_emit_static_artifacts``,
    plugin pre-compile, custom-component re-emit) — those run once per
    compile regardless of page count, so the single-page benchmark
    focuses on the per-page path.

    Args:
        app: a loaded ``rx.App`` with at least one route.
        sess: the live ``CompilerSession`` shared across runs.
        timer: the accumulator for phase samples.
        web_dir: writable directory the rust emitters target.
    """
    from reflex_base.compiler.templates import _render_hooks

    from reflex.compiler import compiler as legacy_compiler
    from reflex.compiler import utils as compiler_utils
    from reflex.compiler.compiler import compile_unevaluated_page
    from reflex.compiler.rust_memo import walk_and_memoize

    app._apply_decorated_pages()

    all_imports: dict[str, list] = {}
    memo_bodies: dict[str, object] = {}
    collected_app_wraps: dict[tuple[int, str], object] = {}

    for route, unev in app._unevaluated_pages.items():
        with timer.measure("compile_unevaluated_page", "python"):
            component = compile_unevaluated_page(route, unev, app.style, app.theme)

        with timer.measure("collect_all_imports_into", "hybrid"):
            sess.collect_all_imports_into(all_imports, component)

        with timer.measure("_get_all_app_wrap_components", "python"):
            collected_app_wraps.update(component._get_all_app_wrap_components())

        with timer.measure("walk_and_memoize", "python"):
            component = walk_and_memoize(component, sess, memo_bodies)

        with timer.measure("_get_all_custom_code", "python"):
            page_custom_code = list(component._get_all_custom_code())

        with timer.measure("_get_all_hooks + _render_hooks", "python"):
            page_hooks_body = _render_hooks(component._get_all_hooks())

        with timer.measure("compile_page_from_component (Rust JSX emit)", "hybrid"):
            rust_js = sess.compile_page_from_component(
                "Bench",
                component,
                route,
                custom_code=page_custom_code,
                hooks_body=page_hooks_body,
            )

        with timer.measure("page write_text", "python"):
            out_path = Path(compiler_utils.get_page_path(route))
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(rust_js)

    # Memo body emission — split into sub-phases so the Python vs Rust
    # split is legible.
    from reflex.compiler.rust_memo import _harvest_pre_hooks, _signature_for

    components_dir = Path(compiler_utils.get_memo_components_dir())
    components_dir.mkdir(parents=True, exist_ok=True)

    with timer.measure("memo body: collect_all_imports_into", "hybrid"):
        for body, _definition in memo_bodies.values():
            sess.collect_all_imports_into(all_imports, body)

    with timer.measure("memo body: _harvest_pre_hooks (Python walk)", "python"):
        prepared: list[tuple[str, str, object, str]] = []
        for name, (body, definition) in memo_bodies.items():
            prepared.append((
                name,
                _signature_for(definition),
                body,
                _harvest_pre_hooks(body),
            ))

    with timer.measure("memo body: compile_memo_from_component (Rust)", "hybrid"):
        emitted_js: list[tuple[str, str]] = []
        for name, signature, body, pre_hooks in prepared:
            js = sess.compile_memo_from_component(
                name, signature, body, pre_hooks=pre_hooks
            )
            emitted_js.append((name, js))

    with timer.measure("memo body: write_text", "python"):
        for name, js in emitted_js:
            (components_dir / f"{name}.jsx").write_text(js)

    # Keep the legacy `_get_all_imports` for app_root → ordered template
    # rendering. Time it so we have visibility, but don't refactor.
    with timer.measure("app_root composition + render", "python"):
        from reflex_base.compiler.templates import _RenderUtils
        from reflex_base.config import get_config

        from reflex.compiler.compiler import (
            _apply_common_imports,
            _resolve_app_wrap_components,
            _resolve_radix_themes_plugin,
        )

        _, radix_themes_plugin = _resolve_radix_themes_plugin(app, get_config().plugins)
        if radix_themes_plugin.enabled and radix_themes_plugin.theme is not None:
            collected_app_wraps[20, "Theme"] = radix_themes_plugin.theme
        app_wrappers = _resolve_app_wrap_components(app, collected_app_wraps)
        app_root = app._app_root(app_wrappers)
        sess.collect_all_imports_into(all_imports, app_root)
        app_root_imports = app_root._get_all_imports()
        _apply_common_imports(app_root_imports)
        _ = "\n".join(
            _RenderUtils.get_import(m)
            for m in compiler_utils.compile_imports(app_root_imports)
        )
        _ = "\n".join(app_root._get_all_custom_code())
        _ = _render_hooks(app_root._get_all_hooks())
        _ = _RenderUtils.render(app_root.render())
        _ = legacy_compiler  # silence unused


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def _setup_web_dir(tmp: Path) -> None:
    """Point Reflex at a writable tmp .web/ for this benchmark.

    Args:
        tmp: directory to use as ``REFLEX_ROOT``.
    """
    from reflex.utils import prerequisites

    web = tmp / ".web"
    web.mkdir(parents=True, exist_ok=True)
    # Monkey-patch get_web_dir so all compiler_utils paths land in tmp.
    prerequisites.get_web_dir = lambda: web  # type: ignore[assignment]


def _compare_python_vs_rust(app, sess, runs: int) -> None:
    """Head-to-head with **sub-step** timing on both paths.

    Each path is broken down into the discrete things it does so the
    exact source of the gap is visible — no assumptions.

    Args:
        app: a loaded ``rx.App`` with at least one route.
        sess: the live Rust ``CompilerSession``.
        runs: number of timed iterations (one warmup discarded).
    """
    from reflex.compiler import utils as compiler_utils
    from reflex.compiler.compiler import (
        _apply_common_imports,
        compile_unevaluated_page,
    )
    from reflex_base.compiler import templates as base_templates
    from reflex_base.compiler.templates import _render_hooks

    route, unev = next(iter(app._unevaluated_pages.items()))

    # Per-sub-step accumulators.
    py_steps: dict[str, list[int]] = {
        "_get_all_imports": [],
        "compile_imports (apply+sort)": [],
        "_get_all_dynamic_imports + sort": [],
        "_get_all_custom_code": [],
        "_get_all_hooks": [],
        "component.render() (recursive)": [],
        "page_template(...)": [],
    }
    rust_steps: dict[str, list[int]] = {
        "collect_all_imports_into (Rust+PyO3)": [],
        "_get_all_custom_code": [],
        "_get_all_hooks + _render_hooks": [],
        "compile_page_from_component (Rust+PyO3)": [],
    }

    for run_idx in range(runs + 1):
        # --- PYTHON PATH ---
        component_py = compile_unevaluated_page(route, unev, app.style, app.theme)

        t0 = _ns()
        imports = component_py._get_all_imports()
        t1 = _ns()
        _apply_common_imports(imports)
        compiled_imports = compiler_utils.compile_imports(imports)
        t2 = _ns()
        dynamic = sorted(component_py._get_all_dynamic_imports())
        t3 = _ns()
        custom = component_py._get_all_custom_code()
        t4 = _ns()
        hooks = component_py._get_all_hooks()
        t5 = _ns()
        rendered = component_py.render()
        t6 = _ns()
        _ = base_templates.page_template(
            imports=compiled_imports,
            dynamic_imports=dynamic,
            custom_codes=custom,
            hooks=hooks,
            render=rendered,
        )
        t7 = _ns()

        py_steps["_get_all_imports"].append(t1 - t0)
        py_steps["compile_imports (apply+sort)"].append(t2 - t1)
        py_steps["_get_all_dynamic_imports + sort"].append(t3 - t2)
        py_steps["_get_all_custom_code"].append(t4 - t3)
        py_steps["_get_all_hooks"].append(t5 - t4)
        py_steps["component.render() (recursive)"].append(t6 - t5)
        py_steps["page_template(...)"].append(t7 - t6)

        # --- RUST PATH ---
        component_rust = compile_unevaluated_page(route, unev, app.style, app.theme)

        t0 = _ns()
        page_imports: dict[str, list] = {}
        sess.collect_all_imports_into(page_imports, component_rust)
        t1 = _ns()
        page_custom_code = list(component_rust._get_all_custom_code())
        t2 = _ns()
        page_hooks_body = _render_hooks(component_rust._get_all_hooks())
        t3 = _ns()
        _ = sess.compile_page_from_component(
            "Bench",
            component_rust,
            route,
            custom_code=page_custom_code,
            hooks_body=page_hooks_body,
        )
        t4 = _ns()

        rust_steps["collect_all_imports_into (Rust+PyO3)"].append(t1 - t0)
        rust_steps["_get_all_custom_code"].append(t2 - t1)
        rust_steps["_get_all_hooks + _render_hooks"].append(t3 - t2)
        rust_steps["compile_page_from_component (Rust+PyO3)"].append(t4 - t3)

        if run_idx == 0:
            # Warmup samples tossed.
            for v in py_steps.values():
                v.pop()
            for v in rust_steps.values():
                v.pop()

    def _summary(steps: dict[str, list[int]], label: str) -> None:
        print()
        print(f"=== {label} ===")
        header = (
            f"{'step':<44}"
            f"{'median':>10}{'mean':>10}{'p95':>10}{'min':>10}{'max':>10}"
        )
        print(header)
        print(
            f"{'':<44}"
            f"{'(ms)':>10}{'(ms)':>10}{'(ms)':>10}{'(ms)':>10}{'(ms)':>10}"
        )
        print("-" * len(header))
        total = 0.0
        for name, ns_samples in steps.items():
            ms = [n / 1_000_000 for n in ns_samples]
            med = statistics.median(ms)
            total += med
            print(
                f"{name:<44}"
                f"{med:>10.3f}{statistics.mean(ms):>10.3f}"
                f"{_p95(ms):>10.3f}{min(ms):>10.3f}{max(ms):>10.3f}"
            )
        print("-" * len(header))
        print(f"{'Total (sum of medians):':<44}{total:>10.3f} ms")
        return total

    print()
    print("=" * 90)
    print("DETAILED PER-STEP COMPARISON")
    print("=" * 90)
    py_total = _summary(py_steps, "Python  _compile_page  — sub-steps")
    rust_total = _summary(rust_steps, "Rust    pipeline  — sub-steps")
    print()
    gap = rust_total - py_total
    pct = gap / py_total * 100 if py_total else 0
    print(
        f"Rust total {rust_total:.3f} ms  |  Python total {py_total:.3f} ms  "
        f"|  Gap = {gap:+.3f} ms  ({pct:+.1f}%)"
    )

    # Pull Rust-side phase timings from the most recent emit so we can
    # see WHERE inside compile_page_from_component the time actually
    # goes. Run one more compile to populate clean counters.
    component_last = compile_unevaluated_page(route, unev, app.style, app.theme)
    page_imports2: dict[str, list] = {}
    sess.collect_all_imports_into(page_imports2, component_last)
    page_custom_code2 = list(component_last._get_all_custom_code())
    page_hooks_body2 = _render_hooks(component_last._get_all_hooks())
    _ = sess.compile_page_from_component(
        "Bench",
        component_last,
        route,
        custom_code=page_custom_code2,
        hooks_body=page_hooks_body2,
    )
    rust_phases = sess.last_phase_timings_ns()

    print()
    print("=" * 90)
    print("RUST-SIDE PHASE BREAKDOWN (inside compile_page_from_component)")
    print("=" * 90)
    print("Last single compile, sampled from thread-local counters.")
    print()
    count_keys = {
        "node_count",
        "element_count",
        "var_count",
        "prop_count",
        "event_handler_count",
    }
    counts = {k: v for k, v in rust_phases.items() if k in count_keys}
    spans = {k: v for k, v in rust_phases.items() if k not in count_keys}

    total_ns = spans.get("read_page_total_ns", 0)
    emit_ns = spans.get("emit_ns", 0)
    sub_phases = [
        (k, v)
        for k, v in spans.items()
        if k not in ("read_page_total_ns", "emit_ns")
    ]
    sub_phases.sort(key=lambda kv: kv[1], reverse=True)

    print(f"{'phase':<32}{'ns':>14}{'ms':>14}")
    print("-" * 60)
    print(f"{'read_page_total_ns':<32}{total_ns:>14}{total_ns / 1e6:>14.3f}")
    print(f"{'  emit_ns (pure Rust)':<32}{emit_ns:>14}{emit_ns / 1e6:>14.3f}")
    for k, v in sub_phases:
        print(f"{'  ' + k:<32}{v:>14}{v / 1e6:>14.3f}")
    accounted = sum(v for _, v in sub_phases) + emit_ns
    unaccounted = max(0, total_ns - accounted)
    print(f"{'  (unaccounted)':<32}{unaccounted:>14}{unaccounted / 1e6:>14.3f}")

    print()
    print(f"{'counter':<32}{'count':>14}")
    print("-" * 46)
    for k in (
        "node_count",
        "element_count",
        "var_count",
        "prop_count",
        "event_handler_count",
    ):
        print(f"{k:<32}{counts.get(k, 0):>14}")

    # Per-call costs derived from the counts. These pinpoint *which*
    # individual operation is dominating once we know how many of each
    # we did.
    print()
    print("per-call costs (ns):")

    def percall(span_key: str, count_key: str) -> str:
        c = counts.get(count_key, 0)
        if not c:
            return "n/a"
        return f"{spans.get(span_key, 0) / c:.0f}"

    print(f"  class_name_ns / element        = {percall('class_name_ns', 'element_count')}")
    print(f"  resolve_tag_ns / element       = {percall('resolve_tag_ns', 'element_count')}")
    print(f"  import_alias_ns / element      = {percall('import_alias_ns', 'element_count')}")
    print(f"  get_props_call_ns / element    = {percall('get_props_call_ns', 'element_count')}")
    print(f"  children_attr_ns / element     = {percall('children_attr_ns', 'element_count')}")
    print(f"  event_triggers_attr_ns / elem  = {percall('event_triggers_attr_ns', 'element_count')}")
    print(f"  needs_ref_ns / element         = {percall('needs_ref_ns', 'element_count')}")
    print(f"  prop_value_getattr_ns / prop   = {percall('prop_value_getattr_ns', 'prop_count')}")
    print(f"  isinstance_var_ns / prop       = {percall('isinstance_var_ns', 'prop_count')}")
    print(f"  var_js_expr_attr_ns / var      = {percall('var_js_expr_attr_ns', 'var_count')}")
    print(f"  read_var_data_ns / var         = {percall('read_var_data_ns', 'var_count')}")


def benchmark(runs: int = 10, scale: int = 1) -> None:
    # CI=1 prevents reflex_enterprise auth gate in docs-style apps.
    os.environ.setdefault("CI", "1")
    os.environ.setdefault("REFLEX_TELEMETRY_ENABLED", "false")

    from reflex.compiler.session import CompilerSession

    timer = PhaseTimer()

    with tempfile.TemporaryDirectory(prefix="reflex_bench_") as tmpstr:
        tmp = Path(tmpstr)
        _setup_web_dir(tmp)

        # Build the app once and the session once — exactly how the CLI
        # uses them across the page loop.
        app = _build_app(scale=scale)
        sess = CompilerSession()

        # Count the tree once for context.
        from reflex.compiler.compiler import compile_unevaluated_page

        first_route, first_unev = next(iter(app._unevaluated_pages.items()))
        evaluated = compile_unevaluated_page(
            first_route, first_unev, app.style, app.theme
        )
        node_count = _count_nodes(evaluated)
        print(f"Bench page: route={first_route!r}  tree={node_count} nodes")
        print(f"Runs: {runs} (1 warmup discarded)")
        print()

        # Section 1: per-phase Rust-pipeline breakdown.
        for _ in range(runs + 1):
            _instrumented_compile_pages(app, sess, timer, tmp / ".web")
        timer.trim_warmup()
        timer.report(runs)

        # Section 2: head-to-head Python vs Rust on the mechanical step.
        _compare_python_vs_rust(app, sess, runs)


def _count_nodes(comp) -> int:
    count = 1
    children = getattr(comp, "children", None) or []
    for child in children:
        try:
            count += _count_nodes(child)
        except Exception:
            count += 1
    return count


if __name__ == "__main__":
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    scale = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    benchmark(runs=runs, scale=scale)
