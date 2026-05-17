"""Microbenchmark: where does compile time actually go?

Splits the per-route compile into four stages so we can see whether the
*framework* (Python user-code + Var/Component construction) or the
*mechanical* part (tree walks + JSX render + template format) dominates.

Stage definitions:

    framework = time of `compile_unevaluated_page(...)`
                — runs the user's `def index(): return rx.box(...)`, evaluates
                every Var, allocates every Component, applies recursive theme
                styles, wraps in Fragment + title/meta. Pure framework cost.
    py_mech   = time of legacy `compiler._compile_page(component)`
                — the mechanical post-tree pipeline: `_get_all_*` walks,
                `component.render()`, `templates.page_template(...)`.
    pyread    = time of `CompilerSession.compile_page_from_component(...)`
                — PyO3 walk over the Component tree + IR build + JSX emit
                in one pass (plan §0b lever (a)).

The decision matrix:

    py_mech ≫ eval+wrap       → mechanical dominates → Rust port pays off
                                without touching the framework. Current
                                `run-rust` architecture is correct.
    eval+wrap ≫ py_mech       → framework dominates → porting framework to
                                Rust is the only way to move the needle.
                                Mechanical Rust work is a small win on top.
    eval+wrap ≈ py_mech       → no single lever; either path is incremental.

Usage:
    uv run python scripts/benchmark_stages.py <app_module>

    e.g.
    uv run python scripts/benchmark_stages.py examples.rust_compiler_demo.rxconfig
"""

from __future__ import annotations

import importlib
import statistics
import sys
import time
from pathlib import Path


def _ns() -> int:
    return time.perf_counter_ns()


def _ms(ns: int) -> float:
    return ns / 1_000_000


def _build_synthetic_app(route_count: int):
    """A self-contained synthetic app driven by tests/benchmarks/fixtures.

    Uses the canonical `_complicated_page` (rich) and `_stateful_page`
    (cond+foreach+match+state) builders so per-route node count is realistic
    (~200-400 nodes/route). Avoids dependency on the docs app, which needs
    auth.
    """
    import reflex as rx
    from tests.benchmarks.fixtures import _complicated_page, _stateful_page

    app = rx.App()
    for i in range(route_count):
        builder = _complicated_page if i % 2 == 0 else _stateful_page

        # Reflex's add_page expects a callable per route — wrap with a fresh
        # closure to avoid identity collisions.
        def make(idx: int, fn=builder):
            def _page():
                return fn()

            _page.__name__ = f"page_{idx}"
            return _page

        app.add_page(make(i), route=f"/page-{i}")
    return app


def benchmark(app_module: str, runs: int = 5) -> None:
    from reflex.compiler import compiler as legacy_compiler
    from reflex.compiler.session import CompilerSession

    # Synthetic shorthand: `synthetic:N` builds an N-route app inline.
    if app_module.startswith("synthetic:"):
        route_count = int(app_module.split(":", 1)[1])
        import_start = _ns()
        app = _build_synthetic_app(route_count)
        import_ns = _ns() - import_start
    else:
        from reflex.utils import prerequisites

        import_start = _ns()
        importlib.import_module(app_module)
        app_info = prerequisites.get_and_validate_app()
        app = app_info.app
        import_ns = _ns() - import_start

    sess = CompilerSession()

    routes = list(app._unevaluated_pages.keys())
    print(f"App: {app_module}")
    print(f"Routes: {len(routes)} — {routes[:5]}{'...' if len(routes) > 5 else ''}")
    print(f"Module import + framework load: {_ms(import_ns):.1f} ms (one-shot)")
    print()

    per_stage = {
        "framework": [],
        "py_mech": [],
        # `pyread` is the only Rust-side stage; it walks the Python
        # Component tree via PyO3 and emits JSX in one pass (plan §0b
        # lever (a)).
        "pyread": [],
    }
    node_counts: list[int] = []

    for run_idx in range(runs):
        for route in routes:
            unev = app._unevaluated_pages[route]

            # Stage 1: framework — full Python user-code + theme + wrap.
            t0 = _ns()
            wrapped = legacy_compiler.compile_unevaluated_page(
                route, unev, app.style, app.theme
            )
            t1 = _ns()

            if run_idx == 0:
                node_counts.append(_count_nodes(wrapped))

            # Stage 2: py_mech — legacy mechanical compile (kept as the
            # Python-side reference; not on the Rust pipeline today).
            t2 = _ns()
            _ = legacy_compiler._compile_page(wrapped)
            t3 = _ns()

            # Stage 3: pyread — PyO3 walk + JSX emit in one pass.
            # Unique ident per-iter so the cache doesn't hide cold cost.
            pyread_ident = (
                f"P_{run_idx}_{route.replace('/', '_').strip('_') or 'index'}"
            )
            t4 = _ns()
            _ = sess.compile_page_from_component(pyread_ident, wrapped, route)
            t5 = _ns()

            per_stage["framework"].append(t1 - t0)
            per_stage["py_mech"].append(t3 - t2)
            per_stage["pyread"].append(t5 - t4)

    if node_counts:
        print(
            f"Tree size: total {sum(node_counts)} nodes, "
            f"median {statistics.median(node_counts)} nodes/route, "
            f"max {max(node_counts)} nodes/route"
        )
        print()

    # Per-route aggregates across all runs.
    print(
        f"{'stage':<10}{'mean ms':>12}{'median ms':>14}{'p95 ms':>12}{'total ms':>14}"
    )
    print("-" * 62)
    totals = {}
    for stage, samples in per_stage.items():
        samples_ms = [s / 1_000_000 for s in samples]
        totals[stage] = sum(samples_ms)
        print(
            f"{stage:<10}"
            f"{statistics.mean(samples_ms):>12.3f}"
            f"{statistics.median(samples_ms):>14.3f}"
            f"{_p95(samples_ms):>12.3f}"
            f"{sum(samples_ms):>14.1f}"
        )

    print()
    py_pipeline = totals["framework"] + totals["py_mech"]
    pyread_pipeline = totals["framework"] + totals["pyread"]
    framework_share = totals["framework"] / py_pipeline * 100
    mechanical_share = totals["py_mech"] / py_pipeline * 100

    print(f"Total Python pipeline (all routes × {runs} runs): {py_pipeline:>8.1f} ms")
    print(
        f"Total pyread pipeline (all routes × {runs} runs): {pyread_pipeline:>8.1f} ms"
    )
    print(
        f"Pyread speedup over Python (mechanical only): {totals['py_mech'] / max(totals['pyread'], 0.001):.1f}×"
    )
    print()
    print(f"Framework share of Python pipeline: {framework_share:.1f}%")
    print(f"Mechanical share of Python pipeline: {mechanical_share:.1f}%")
    print()
    if framework_share > 70:
        print(
            "→ Framework cost dominates. Rust replacing mechanical work is a "
            "small win. Porting Var/Component to Rust would be the lever — "
            "but that's the non-hackable direction."
        )
    elif mechanical_share > 70:
        print(
            "→ Mechanical cost dominates. Rust replacing it (current "
            "architecture) is the right lever. Framework can stay Python "
            "without sacrificing the speedup."
        )
    else:
        print("→ No single lever; both stages contribute meaningfully.")


def _count_nodes(comp) -> int:
    """Count Components in a tree. Best-effort — used only for sizing context."""
    count = 1
    children = getattr(comp, "children", None) or []
    for child in children:
        try:
            count += _count_nodes(child)
        except Exception:
            count += 1
    return count


def _p95(samples: list[float]) -> float:
    if not samples:
        return 0.0
    s = sorted(samples)
    idx = int(0.95 * (len(s) - 1))
    return s[idx]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: benchmark_stages.py <app_module> [runs]")
        print()
        print("Examples:")
        print("  uv run python scripts/benchmark_stages.py rust_compiler_demo")
        print("  uv run python scripts/benchmark_stages.py reflex_docs 5")
        sys.exit(2)

    app_module = sys.argv[1]
    runs = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    benchmark(app_module, runs=runs)
