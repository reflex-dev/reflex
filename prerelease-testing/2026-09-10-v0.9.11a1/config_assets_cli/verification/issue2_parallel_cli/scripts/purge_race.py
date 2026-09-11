"""Minimal repro: reflex.compiler.compiler.purge_web_pages_dir() is check-then-act.

Run from an app directory that already has a .web/ (any reflex app):

    REFLEX_ENV_MODE=prod REFLEX_TELEMETRY_ENABLED=false \
      <venv>/bin/python purge_race.py [workers] [iterations]

Each worker repeatedly repopulates .web/app/routes/ and then calls
purge_web_pages_dir(), which is exactly what `reflex export` /
`reflex run --env prod` do on every compile. Any non-zero exit is the
FileNotFoundError from shutil.rmtree racing another process.
"""

import multiprocessing as mp
import os
import sys
import traceback
from pathlib import Path

import reflex

assert "/envs/" in reflex.__file__, reflex.__file__

from reflex.compiler.compiler import purge_web_pages_dir  # noqa: E402
from reflex.utils.prerequisites import get_web_dir  # noqa: E402


def worker(idx: int, iterations: int) -> str:
    routes = Path(get_web_dir()) / "app" / "routes"
    try:
        for i in range(iterations):
            for d in range(6):
                p = routes / f"race{d}" / "nested"
                p.mkdir(parents=True, exist_ok=True)
                (p / f"page{i}.jsx").write_text("export default () => null;\n")
            purge_web_pages_dir()
    except Exception:
        return f"worker {idx} FAILED:\n{traceback.format_exc()}"
    return ""


if __name__ == "__main__":
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    iterations = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    print("reflex:", reflex.__file__)
    print("cwd:", os.getcwd(), "web dir:", get_web_dir())
    with mp.Pool(workers) as pool:
        results = pool.starmap(worker, [(i, iterations) for i in range(workers)])
    failures = [r for r in results if r]
    for r in failures:
        print(r)
    print(f"{len(failures)}/{workers} workers raised")
    sys.exit(1 if failures else 0)
