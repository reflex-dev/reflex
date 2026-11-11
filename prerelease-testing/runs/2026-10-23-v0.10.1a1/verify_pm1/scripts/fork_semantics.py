"""Pure-Python (no reflex) probe of what fork does to random / Random() / uuid4 / secrets / threads.

Separates: (a) module-level values computed once pre-fork (expected identical in any preload model),
(b) the global `random` module instance (CPython registers an at-fork reseed via os.register_at_fork),
(c) a user `random.Random()` instance (NOT reseeded), (d) uuid.uuid4() / secrets (os.urandom: always fresh),
(e) threads started before the fork (POSIX: only the forking thread survives in the child).
"""
import json, os, random, secrets, sys, threading, time, uuid, multiprocessing as mp

MODULE_RANDOM = random.random()
MODULE_UUID = str(uuid.uuid4())
PRNG = random.Random()
PRNG_SEEDED = random.Random(42)
TICKS = {"n": 0}
def _tick():
    while True:
        TICKS["n"] += 1; time.sleep(0.05)
t = threading.Thread(target=_tick, daemon=True); t.start(); time.sleep(0.2)

def child(q):
    time.sleep(0.3)
    q.put({
        "pid": os.getpid(),
        "module_random": MODULE_RANDOM, "module_uuid": MODULE_UUID[:8],
        "global_random_now": random.random(),
        "prng_now": PRNG.random(), "prng_seeded_now": PRNG_SEEDED.random(),
        "uuid4_now": str(uuid.uuid4())[:8], "secrets_now": secrets.token_hex(4),
        "ticker_alive": t.is_alive(), "ticks_at_fork": TICKS["n"], "ticks_after_300ms": TICKS["n"],
        "threads": [x.name for x in threading.enumerate()],
    })

if __name__ == "__main__":
    ctx = mp.get_context(sys.argv[1] if len(sys.argv) > 1 else "fork")
    q = ctx.Queue()
    ps = [ctx.Process(target=child, args=(q,)) for _ in range(4)]
    [p.start() for p in ps]
    rows = [q.get(timeout=10) for _ in ps]
    [p.join() for p in ps]
    for r in rows: print(json.dumps(r))
    def distinct(k): return len({r[k] for r in rows})
    print("SUMMARY", json.dumps({"start_method": ctx.get_start_method(), "python": sys.version.split()[0],
        "distinct_module_random": distinct("module_random"), "distinct_module_uuid": distinct("module_uuid"),
        "distinct_global_random_now": distinct("global_random_now"), "distinct_prng_now": distinct("prng_now"),
        "distinct_prng_seeded_now": distinct("prng_seeded_now"),
        "distinct_uuid4_now": distinct("uuid4_now"), "distinct_secrets_now": distinct("secrets_now"),
        "ticker_alive_in_children": sum(r["ticker_alive"] for r in rows),
        "parent_ticker_alive": t.is_alive()}))
