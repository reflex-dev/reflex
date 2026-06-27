"""Spike: Salsa-style persistent page cache on the real compile path.

Salsa = demand-driven, dependency-tracked incremental memoization. For a page
compiler the practical form is: fingerprint each page's *source inputs* (the
markdown/page-module content + shared-template version), persist compiled
outputs to disk keyed by that fingerprint, and on the next build recompile only
pages whose fingerprint changed. The fingerprint is computed WITHOUT building
the tree, so an unchanged page skips its ENTIRE cost (build + render +
aggregation + template) — the automatic, content-addressed generalization of
docs/app's manual `whitelist.py`, and what makes full/CI builds incremental.

The real docs app can't import here (private deps), so this runs on the
synthetic docs-like project from spike_caching.py with the real
`compiler._compile_page`. The SalsaCache + harness are written to drop onto the
real app: replace `page_source`/`compile_page` with the doc file hash + the real
page compile.

Run:  uv run python experimental/reflex-compiler-core/salsa_spike.py
"""

import gc
import hashlib
import pickle
import time
from pathlib import Path

from reflex.compiler import compiler

import spike_caching as proj

N_PAGES = 100
CACHE_PATH = Path("/tmp/claude-0/-home-user-reflex/bbc2fa43-3195-51ee-ac40-a3e16478d6d8/scratchpad/salsa_cache.pkl")


def fingerprint(source: str) -> str:
    return hashlib.sha256(source.encode()).hexdigest()


def page_source(route: int, edited: set[int]) -> str:
    """The source inputs that determine a page's output (what a real cache hashes:
    the doc/page-module content + shared template version). Editing a page bumps it."""
    version = 2 if route in edited else 1
    return f"route={route};content_version={version};template=v1"


def compile_page(route: int) -> str:
    # build (Component.create) + render + aggregation + template — the full cost.
    return compiler._compile_page(proj.page(route))


class SalsaCache:
    """Disk-persistent, content-addressed page cache."""

    def __init__(self, path: Path):
        self.path = path
        self.entries: dict[int, tuple[str, str]] = {}  # route -> (fingerprint, output)
        if path.exists():
            self.entries = pickle.loads(path.read_bytes())

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(pickle.dumps(self.entries))

    def build(self, edited: set[int]) -> tuple[int, int]:
        hits = misses = 0
        for route in range(N_PAGES):
            fp = fingerprint(page_source(route, edited))
            cached = self.entries.get(route)
            if cached is not None and cached[0] == fp:
                _ = cached[1]  # cache hit: reuse stored output, no compile
                hits += 1
            else:
                self.entries[route] = (fp, compile_page(route))
                misses += 1
        return hits, misses


def _t(fn):
    gc.collect(); gc.disable()
    t0 = time.perf_counter()
    out = fn()
    dt = time.perf_counter() - t0
    gc.enable()
    return dt, out


def main():
    # fresh start
    CACHE_PATH.unlink(missing_ok=True)
    compiler._compile_page(proj.page(0))  # warm imports

    # Build 1: cold, empty cache -> everything compiles.
    c1 = SalsaCache(CACHE_PATH)
    t_cold, (h1, m1) = _t(lambda: c1.build(edited=set()))
    c1.save()
    print(f"build 1 (cold, empty cache)   : {t_cold*1e3:8.1f} ms   hits={h1:3d} misses={m1:3d}")

    # Build 2: nothing changed (new process would reload from disk) -> all hits.
    c2 = SalsaCache(CACHE_PATH)
    t_noop, (h2, m2) = _t(lambda: c2.build(edited=set()))
    print(f"build 2 (no changes)          : {t_noop*1e3:8.1f} ms   hits={h2:3d} misses={m2:3d}   ({t_cold/max(t_noop,1e-6):.0f}x)")

    # Build 3: edit ONE page -> only it recompiles.
    c3 = SalsaCache(CACHE_PATH)
    t_one, (h3, m3) = _t(lambda: c3.build(edited={42}))
    c3.save()
    print(f"build 3 (edit 1 page)         : {t_one*1e3:8.1f} ms   hits={h3:3d} misses={m3:3d}   ({t_cold/max(t_one,1e-6):.0f}x)")

    # Build 4: edit five pages.
    c4 = SalsaCache(CACHE_PATH)
    t_five, (h4, m4) = _t(lambda: c4.build(edited={1, 9, 42, 70, 99}))
    print(f"build 4 (edit 5 pages)        : {t_five*1e3:8.1f} ms   hits={h4:3d} misses={m4:3d}   ({t_cold/max(t_five,1e-6):.0f}x)")

    print(f"\nfull cold build = {t_cold*1e3:.0f} ms; incremental rebuild scales with #changed pages,")
    print("not project size — the automatic, persistent form of docs/app's whitelist.")


if __name__ == "__main__":
    main()
