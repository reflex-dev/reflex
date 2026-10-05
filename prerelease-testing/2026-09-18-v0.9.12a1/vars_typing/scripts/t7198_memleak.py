"""#7198: var operations must not keep permanent references (_global_vars leak) and be faster."""
import gc, json, os, sys, time, resource
import reflex as rx
assert "/envs/" in rx.__file__, rx.__file__
from reflex_base.vars.base import _global_vars

def rss_kb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

class S(rx.State):
    count: int = 0
    name: str = "hello"
    flag: bool = False
    items: list[int] = [1, 2, 3]
    obj: dict[str, int] = {"a": 1}

N = int(os.environ.get("N", "40000"))
SAMPLE = N // 5

OPS = {
    "add": lambda i: S.count + i,
    "to_string": lambda i: (S.count + i).to_string(),
    "bool_and": lambda i: (S.count > i) & S.flag,
    "index": lambda i: S.items[i % 3],
    "str_concat": lambda i: S.name + str(i),
    "obj_get": lambda i: S.obj["a"] + i,
    "cond": lambda i: rx.cond(S.count > i, "yes", "no"),
    "upper": lambda i: S.name.upper() + str(i),
}

report = {"version": rx.constants.Reflex.VERSION, "N": N, "ops": {}}
for name, fn in OPS.items():
    gc.collect()
    g0 = len(_global_vars)
    r0 = rss_kb()
    samples = []
    t0 = time.perf_counter()
    for i in range(N):
        fn(i)
        if (i + 1) % SAMPLE == 0:
            samples.append((i + 1, len(_global_vars) - g0, rss_kb() - r0))
    dt = time.perf_counter() - t0
    gc.collect()
    report["ops"][name] = {
        "sec": round(dt, 4),
        "us_per_op": round(dt / N * 1e6, 3),
        "global_vars_growth": len(_global_vars) - g0,
        "samples_(n, dglobal, drss_kb)": samples,
    }
report["global_vars_total_end"] = len(_global_vars)
print(json.dumps(report, indent=2))
