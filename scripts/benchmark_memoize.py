"""Benchmark the memoize-plugin cost for a Reflex app.

Pins the timings against a baseline so each iteration's port work is
measurable. Memoization is documented in plan §0 as the dominant bucket
on large apps (~47% on the docs app), so every speedup needs to be
compared against this baseline.

Usage::

    cd <app-dir>             # e.g. docs/app
    CI=1 uv run python <repo>/scripts/benchmark_memoize.py
    CI=1 uv run python <repo>/scripts/benchmark_memoize.py --runs 3
    CI=1 uv run python <repo>/scripts/benchmark_memoize.py --check          # CI mode
    CI=1 uv run python <repo>/scripts/benchmark_memoize.py --update-baseline

Output (per run, then median):
    wall                 total compile wall-clock
    decide               _should_memoize cumtime
    build_wrapper        _build_wrapper cumtime
    passthrough_memo     create_passthrough_component_memo cumtime
    compile_memo_files   _compile_memo_components cumtime
    leave_component      memoize.leave_component cumtime

The baseline is per-app, keyed by the rxconfig's ``app_name``. Stored at
``<app-dir>/.memoize_baseline.json``.

Exit codes:
    0 — all buckets within ``--threshold`` (default 5%) of baseline.
    1 — at least one bucket regressed beyond the threshold.
    2 — invocation error (no app, no baseline, etc.).
"""

from __future__ import annotations

import argparse
import cProfile
import json
import pstats
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path


_TRACKED_FUNCTIONS = {
    # bucket name → substring matched against pstats keys (`file:line(name)`).
    "decide": "memoize.py:120(_should_memoize)",
    "build_wrapper": "memoize.py:329(_build_wrapper)",
    "passthrough_memo": "memo.py:1017(create_passthrough_component_memo)",
    "compile_memo_files": "compiler.py:396(_compile_memo_components)",
    "leave_component": "memoize.py:276(leave_component)",
}


@dataclass
class Sample:
    wall_ms: float
    decide_ms: float
    build_wrapper_ms: float
    passthrough_memo_ms: float
    compile_memo_files_ms: float
    leave_component_ms: float


def _cum_ms(stats: pstats.Stats, needle: str) -> float:
    """Sum cumtime (in ms) across pstats keys whose label contains ``needle``."""
    total = 0.0
    for key, (_cc, _nc, _tt, ct, _cs) in stats.stats.items():  # type: ignore[attr-defined]
        label = f"{key[0]}:{key[1]}({key[2]})"
        if needle in label:
            total += ct
    return total * 1000.0


def measure_once() -> Sample:
    from reflex.utils import prerequisites

    prof = cProfile.Profile()
    t = time.perf_counter()
    prof.enable()
    prerequisites.get_compiled_app(trigger="bench_memoize", reload=True)
    prof.disable()
    wall = (time.perf_counter() - t) * 1000.0
    stats = pstats.Stats(prof)
    return Sample(
        wall_ms=wall,
        decide_ms=_cum_ms(stats, _TRACKED_FUNCTIONS["decide"]),
        build_wrapper_ms=_cum_ms(stats, _TRACKED_FUNCTIONS["build_wrapper"]),
        passthrough_memo_ms=_cum_ms(stats, _TRACKED_FUNCTIONS["passthrough_memo"]),
        compile_memo_files_ms=_cum_ms(stats, _TRACKED_FUNCTIONS["compile_memo_files"]),
        leave_component_ms=_cum_ms(stats, _TRACKED_FUNCTIONS["leave_component"]),
    )


def aggregate(samples: list[Sample]) -> Sample:
    fields = ("wall_ms", "decide_ms", "build_wrapper_ms", "passthrough_memo_ms", "compile_memo_files_ms", "leave_component_ms")
    return Sample(**{
        f: statistics.median([getattr(s, f) for s in samples]) for f in fields
    })


def baseline_path(app_dir: Path) -> Path:
    return app_dir / ".memoize_baseline.json"


def load_baseline(app_dir: Path) -> Sample | None:
    p = baseline_path(app_dir)
    if not p.is_file():
        return None
    return Sample(**json.loads(p.read_text()))


def save_baseline(app_dir: Path, s: Sample) -> None:
    baseline_path(app_dir).write_text(json.dumps(asdict(s), indent=2) + "\n")


def _fmt(name: str, current: float, baseline: float | None, threshold: float) -> str:
    if baseline is None:
        return f"  {name:<22}  {current:>8.1f} ms"
    delta = (current - baseline) / max(baseline, 1.0)
    flag = " "
    if abs(delta) > threshold:
        flag = "✗" if delta > 0 else "✓"
    pct = f"{delta * 100:+.1f}%"
    return f"  {name:<22}  {current:>8.1f} ms  (baseline {baseline:>7.1f} ms, {pct:>7})  {flag}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--threshold", type=float, default=0.05, help="regression threshold (5%% default)")
    parser.add_argument("--check", action="store_true", help="CI mode: exit 1 on regression")
    parser.add_argument("--update-baseline", action="store_true")
    args = parser.parse_args()

    app_dir = Path.cwd().resolve()
    if not (app_dir / "rxconfig.py").is_file():
        print("must run from a Reflex app directory (rxconfig.py missing)", file=sys.stderr)
        return 2

    # Warm the import cache so the first sample isn't an outlier.
    from reflex.utils import prerequisites

    prerequisites.get_compiled_app(trigger="bench_warm")

    samples: list[Sample] = []
    for i in range(args.runs):
        s = measure_once()
        samples.append(s)
        print(f"  run {i+1}: wall={s.wall_ms:.0f} ms  decide={s.decide_ms:.0f}  "
              f"build={s.build_wrapper_ms:.0f}  passthrough={s.passthrough_memo_ms:.0f}  "
              f"compile_files={s.compile_memo_files_ms:.0f}  leave={s.leave_component_ms:.0f}")

    median = aggregate(samples)

    print(f"\n=== median over {args.runs} run(s) ({app_dir.name}) ===")
    baseline = None if args.update_baseline else load_baseline(app_dir)
    rows = [
        ("wall",                 median.wall_ms),
        ("decide",               median.decide_ms),
        ("leave_component",      median.leave_component_ms),
        ("build_wrapper",        median.build_wrapper_ms),
        ("passthrough_memo",     median.passthrough_memo_ms),
        ("compile_memo_files",   median.compile_memo_files_ms),
    ]
    for name, current in rows:
        b = getattr(baseline, f"{name if name == 'wall' else name}_ms", None) if baseline else None
        print(_fmt(name, current, b, args.threshold))

    if args.update_baseline:
        save_baseline(app_dir, median)
        print(f"\nwrote baseline → {baseline_path(app_dir)}")
        return 0

    if args.check:
        if baseline is None:
            print("no baseline; run --update-baseline first", file=sys.stderr)
            return 2
        failed = False
        for name, current in rows:
            b = getattr(baseline, f"{name}_ms", None)
            if b is None:
                continue
            if (current - b) / max(b, 1.0) > args.threshold:
                failed = True
        if failed:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
