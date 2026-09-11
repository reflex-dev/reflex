"""#7039 in two halves: the concurrent-first-create race, and the stale-link repoint.

Usage: python race_assets2.py <trials> <workers>
"""

import multiprocessing as mp
import os
import shutil
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "sharedasset")
EXT = os.path.join(APP, "assets", "external")
LINK = os.path.join(EXT, "sharedasset", "sharedasset", "lib.js")


def worker(barrier, q):
    """Wait on the barrier, then register the shared asset exactly once."""
    os.chdir(APP)
    sys.path.insert(0, APP)
    from sharedasset.sharedasset import index  # noqa: PLC0415

    index  # noqa: B018  (import cost paid before the barrier)
    barrier.wait()
    try:
        index()
        q.put(None)
    except Exception:  # noqa: BLE001
        q.put(traceback.format_exc(limit=4).strip().splitlines()[-1])


def race(trials: int, workers: int) -> None:
    """Run `trials` simultaneous-first-create races."""
    ctx = mp.get_context("spawn")
    failures, seen = 0, {}
    for _ in range(trials):
        shutil.rmtree(EXT, ignore_errors=True)
        barrier = ctx.Barrier(workers)
        q = ctx.Queue()
        procs = [ctx.Process(target=worker, args=(barrier, q)) for _ in range(workers)]
        for p in procs:
            p.start()
        for _ in procs:
            r = q.get()
            if r:
                failures += 1
                seen[r] = seen.get(r, 0) + 1
        for p in procs:
            p.join()
    print(f"RACE trials={trials} workers={workers} registrations={trials * workers} failures={failures}")
    for k, v in seen.items():
        print(f"   x{v} {k}")


def repoint() -> None:
    """Point the link at the wrong file, then re-register and see if it is fixed."""
    shutil.rmtree(EXT, ignore_errors=True)
    os.chdir(APP)
    sys.path.insert(0, APP)
    from sharedasset.sharedasset import index  # noqa: PLC0415

    index()
    target_before = os.path.realpath(LINK)
    os.remove(LINK)
    os.symlink(os.path.join(APP, "sharedasset", "other.js"), LINK)
    print("REPOINT before:", os.path.basename(os.path.realpath(LINK)))
    index()
    after = os.path.realpath(LINK)
    print("REPOINT after: ", os.path.basename(after),
          "=> FIXED" if after == target_before else "=> STILL WRONG")
    print("REPOINT content:", open(LINK).read().strip())


if __name__ == "__main__":
    race(int(sys.argv[1]), int(sys.argv[2]))
    repoint()
