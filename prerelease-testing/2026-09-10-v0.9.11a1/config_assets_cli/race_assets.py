"""Reproduce #7039: many processes registering the same rx.asset(shared=True) at once.

Usage: python race_assets.py <n_workers> <iterations>
"""

import multiprocessing as mp
import os
import shutil
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "sharedasset")


def worker(idx: int, iterations: int, q):
    """Register the shared asset repeatedly and report any exception."""
    os.chdir(APP)
    sys.path.insert(0, APP)
    from sharedasset.sharedasset import index  # noqa: PLC0415

    errs = []
    for _ in range(iterations):
        try:
            index()
        except Exception:  # noqa: BLE001
            errs.append(traceback.format_exc(limit=3))
    q.put((idx, errs))


def main():
    """Run the race."""
    n, iterations = int(sys.argv[1]), int(sys.argv[2])
    ext = os.path.join(APP, "assets", "external")
    shutil.rmtree(ext, ignore_errors=True)
    ctx = mp.get_context("spawn")
    q = ctx.Queue()
    procs = [ctx.Process(target=worker, args=(i, iterations, q)) for i in range(n)]
    for p in procs:
        p.start()
    results = [q.get() for _ in procs]
    for p in procs:
        p.join()
    total = sum(len(e) for _, e in results)
    print(f"workers={n} iterations={iterations} failures={total}")
    seen = set()
    for _, errs in results:
        for e in errs:
            last = e.strip().splitlines()[-1]
            if last not in seen:
                seen.add(last)
                print("  ", last)
    for root, _dirs, files in os.walk(ext):
        for f in files:
            p = os.path.join(root, f)
            print("  link:", os.path.relpath(p, ext), "->",
                  os.path.realpath(p).split("/sharedasset/")[-1] if os.path.islink(p) else "(regular file)")


if __name__ == "__main__":
    main()
