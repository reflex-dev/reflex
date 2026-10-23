"""#7052 probe: concurrent update_json_file() from N processes on one reflex.json-like file, with a reader
checking that the file is always complete JSON. Runs the INSTALLED reflex (venv passed as argv[1]).

Usage: <venv>/bin/python -I json_lock_probe.py <venv> <workdir> [procs=8] [updates=40] [--reflex-dir DIR]
Prints a JSON summary: keys_expected vs keys_present (lost updates = unlocked fallback or a bug), invalid_reads
(reader saw a partial document), tmp files left behind, lock dir.
"""

import json
import multiprocessing
import os
import sys
import time


def setup(venv, workdir):
    os.environ.setdefault("REFLEX_TELEMETRY_ENABLED", "false")
    os.makedirs(workdir, exist_ok=True)
    os.chdir(workdir)
    import reflex

    assert f"/envs/{venv}/" in reflex.__file__, reflex.__file__
    from reflex.utils import path_ops

    return path_ops


def writer(venv, workdir, i, updates, reflex_dir):
    if reflex_dir:
        os.environ["REFLEX_DIR"] = reflex_dir
    path_ops = setup(venv, workdir)
    target = os.path.join(workdir, "reflex.json")
    for k in range(updates):
        path_ops.update_json_file(target, {f"p{i}_k{k}": os.getpid()})


def reader(target, stop_event, q):
    bad = 0
    reads = 0
    samples = []
    while not stop_event.is_set():
        try:
            with open(target) as f:
                s = f.read()
            if s:
                reads += 1
                json.loads(s)
        except FileNotFoundError:
            pass
        except Exception as e:  # noqa: BLE001
            bad += 1
            if len(samples) < 3:
                samples.append(str(e)[:80])
        time.sleep(0.002)
    q.put((reads, bad, samples))


def main():
    venv = sys.argv[1]
    workdir = sys.argv[2]
    procs = int(sys.argv[3]) if len(sys.argv) > 3 and not sys.argv[3].startswith("--") else 8
    updates = int(sys.argv[4]) if len(sys.argv) > 4 and not sys.argv[4].startswith("--") else 40
    reflex_dir = sys.argv[sys.argv.index("--reflex-dir") + 1] if "--reflex-dir" in sys.argv else None
    if reflex_dir:
        os.environ["REFLEX_DIR"] = reflex_dir
    os.makedirs(workdir, exist_ok=True)
    target = os.path.join(workdir, "reflex.json")
    if os.path.exists(target):
        os.remove(target)
    ctx = multiprocessing.get_context("spawn")
    q = ctx.Queue()
    stop_event = ctx.Event()
    t0 = time.monotonic()
    rd = ctx.Process(target=reader, args=(target, stop_event, q))
    rd.start()
    ps = [ctx.Process(target=writer, args=(venv, workdir, i, updates, reflex_dir)) for i in range(procs)]
    [p.start() for p in ps]
    [p.join() for p in ps]
    dt = time.monotonic() - t0
    stop_event.set()
    reads, bad, samples = 0, 0, []
    try:
        reads, bad, samples = q.get(timeout=10)
    except Exception:  # noqa: BLE001
        pass
    rd.join(5)
    doc = json.load(open(target)) if os.path.exists(target) else {}
    lock_dir = os.path.join(reflex_dir or os.path.expanduser("~/.local/share/reflex"), "locks")
    tmp_left = [f for f in os.listdir(workdir) if f.startswith(".reflex.json.") and f.endswith(".tmp")]
    print(json.dumps({
        "venv": venv, "procs": procs, "updates": updates, "seconds": round(dt, 2),
        "keys_expected": procs * updates, "keys_present": len(doc), "lost": procs * updates - len(doc),
        "reader_reads": reads, "invalid_reads": bad, "invalid_samples": samples, "lock_dir": lock_dir,
        "lock_dir_is_dir": os.path.isdir(lock_dir), "tmp_files_left": tmp_left, "writer_exitcodes": [p.exitcode for p in ps],
    }))


if __name__ == "__main__":
    main()
