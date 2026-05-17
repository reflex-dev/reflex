"""Benchmark driver for the Rust compiler pipeline. See plan §6a.

Reads the corpus under ``tests/codegen_corpus/``, drives each fixture
through the Component → IR → Rust → JS pipeline, and reports cold + warm
wall-clock plus per-fixture peak RSS. Used both by humans (run it locally
to see the numbers) and by CI (``--check`` reads the baseline and exits
non-zero if any fixture regresses by >5%).

Examples::

    uv run python scripts/benchmark_compile.py                 # all fixtures
    uv run python scripts/benchmark_compile.py 06_cond         # one fixture
    uv run python scripts/benchmark_compile.py --runs 10
    uv run python scripts/benchmark_compile.py --check         # CI mode
    uv run python scripts/benchmark_compile.py --update-baseline

The script does NOT invoke the legacy Python compiler — those numbers come
from the existing ``scripts/profile_compilation_hotspots.py``. This script
exclusively measures the Rust path, which is what §13 cares about.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import resource
import statistics
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = REPO_ROOT / "tests" / "codegen_corpus"
BASELINE_PATH = CORPUS_DIR / "baseline.json"
REGRESSION_THRESHOLD = 0.05  # 5% per plan §6
NOISE_FLOOR_US = 5.0  # below this, percentage regressions are noise


# Ensure the repo is on sys.path so we can import `reflex.compiler.ir.*`.
sys.path.insert(0, str(REPO_ROOT))


@dataclass
class FixtureResult:
    name: str
    cold_us: float
    warm_us: float
    peak_rss_kb: int
    output_bytes: int


def _peak_rss_kb() -> int:
    """Linux returns RSS in kB from getrusage; macOS returns bytes. Best-effort."""
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return int(raw / 1024)
    return int(raw)


def bench_one(fixture, runs: int) -> FixtureResult:
    from reflex.compiler.session import CompilerSession

    try:
        sess = CompilerSession()
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    component = fixture.build()

    # Cold: clear the cache, measure one run.
    sess.clear_cache()
    gc.collect()
    t0 = time.perf_counter_ns()
    js = sess.compile_page_from_component(fixture.ident, component, fixture.route)
    cold_ns = time.perf_counter_ns() - t0

    # Warm: median of N subsequent runs, all hitting the cache.
    samples = []
    for _ in range(runs):
        t0 = time.perf_counter_ns()
        sess.compile_page_from_component(fixture.ident, component, fixture.route)
        samples.append(time.perf_counter_ns() - t0)
    samples.sort()
    warm_ns = samples[len(samples) // 2]

    return FixtureResult(
        name=fixture.name,
        cold_us=cold_ns / 1000.0,
        warm_us=warm_ns / 1000.0,
        peak_rss_kb=_peak_rss_kb(),
        output_bytes=len(js.encode("utf-8")),
    )


def load_baseline() -> dict[str, dict]:
    if not BASELINE_PATH.is_file():
        return {}
    return json.loads(BASELINE_PATH.read_text())


def write_baseline(results: list[FixtureResult]) -> None:
    payload = {r.name: asdict(r) for r in results}
    BASELINE_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def check_regressions(results: list[FixtureResult]) -> int:
    baseline = load_baseline()
    if not baseline:
        print("no baseline.json — run with --update-baseline first", file=sys.stderr)
        return 1
    failures = 0
    for r in results:
        prior = baseline.get(r.name)
        if not prior:
            print(f"  [warn] {r.name}: no baseline entry, skipping")
            continue
        # warm_us is the regression-gating metric per plan §6a.
        prior_warm = prior["warm_us"]
        ratio = (r.warm_us - prior_warm) / max(prior_warm, 1.0)
        # Below the noise floor, sub-microsecond variance is not a real
        # signal — pytest-style flakes would dominate. We still print the
        # numbers so humans can see drift, but the test doesn't fail.
        below_floor = max(r.warm_us, prior_warm) < NOISE_FLOOR_US
        status = "ok"
        if ratio > REGRESSION_THRESHOLD and not below_floor:
            failures += 1
            status = f"FAIL (+{ratio*100:.1f}%)"
        elif ratio > REGRESSION_THRESHOLD:
            status = f"ok (below {NOISE_FLOOR_US:.0f}µs noise floor, +{ratio*100:.1f}%)"
        print(
            f"  {r.name:<24}  cold {r.cold_us:>8.1f}µs  warm {r.warm_us:>8.1f}µs  "
            f"baseline {prior_warm:>8.1f}µs  {status}"
        )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "fixture",
        nargs="?",
        help="run a single fixture by directory name (e.g. 06_cond). default: all",
    )
    parser.add_argument("--runs", type=int, default=5, help="warm-run sample size (median)")
    parser.add_argument("--check", action="store_true", help="exit 1 on >5%% warm regression")
    parser.add_argument("--update-baseline", action="store_true", help="overwrite baseline.json")
    args = parser.parse_args()

    # Lazy import to keep --help fast and free of project-dep noise.
    from tests.codegen_corpus._runner import discover

    fixtures = discover()
    if args.fixture:
        fixtures = [f for f in fixtures if f.name == args.fixture]
        if not fixtures:
            print(f"no fixture named {args.fixture!r}", file=sys.stderr)
            return 1

    print(f"running {len(fixtures)} fixture(s), {args.runs} warm samples each\n")
    results: list[FixtureResult] = []
    for f in fixtures:
        r = bench_one(f, args.runs)
        results.append(r)
        print(
            f"  {r.name:<24}  cold {r.cold_us:>8.1f}µs  warm {r.warm_us:>8.1f}µs  "
            f"out {r.output_bytes:>5}B  rss {r.peak_rss_kb:>6}kB"
        )

    if args.update_baseline:
        write_baseline(results)
        print(f"\nwrote baseline: {BASELINE_PATH}")
        return 0

    if args.check:
        print()
        failures = check_regressions(results)
        if failures:
            print(f"\nFAILED: {failures} fixture(s) regressed by >5%", file=sys.stderr)
            return 1
        print("\nall fixtures within 5% of baseline.")
        return 0

    if len(results) > 1:
        cold = [r.cold_us for r in results]
        warm = [r.warm_us for r in results]
        print(
            f"\nsummary: cold median {statistics.median(cold):>6.1f}µs  "
            f"warm median {statistics.median(warm):>6.1f}µs  "
            f"warm geomean {statistics.geometric_mean(warm):>6.1f}µs"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
