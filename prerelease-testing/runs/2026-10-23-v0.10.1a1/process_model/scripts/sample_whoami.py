"""sample_whoami.py <base_url> [n=60] [--json out]: hit /api/whoami n times, aggregate per worker pid.

Driver venv. Prints per-pid: imported_in_this_process, ticker/timer liveness, lifespan, start method,
module-level random/uuid (identical across workers?), live random values, redis/db, qlistener.
"""

import json
import sys
import urllib.request

base = sys.argv[1].rstrip("/")
n = int(sys.argv[2]) if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else 60
out = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
per = {}
errors = 0
for _ in range(n):
    try:
        with opener.open(f"{base}/api/whoami", timeout=5) as r:
            d = json.load(r)
    except Exception as e:  # noqa: BLE001
        errors += 1
        print("ERR", e)
        continue
    p = per.setdefault(d["pid"], {"samples": [], "random_now": set(), "prng_now": set(), "uuid_now": set()})
    p["samples"].append(d)
    p["random_now"].add(d["random_now"])
    p["prng_now"].add(d["prng_now"])
    p["uuid_now"].add(d["uuid_now"])
rows = []
for pid, p in sorted(per.items()):
    first, last = p["samples"][0], p["samples"][-1]
    rows.append({
        "pid": pid, "ppid": last["ppid"], "n": len(p["samples"]),
        "imported_here": last["imported_in_this_process"], "import_pid": last["import_pid"],
        "start_method": last["start_method"], "start_method_at_import": last["start_method_at_import"],
        "module_random": last["module_random"], "module_uuid": last["module_uuid"][:8], "module_token": last["module_token"],
        "first_random_now": first["random_now"], "first_prng_now": first["prng_now"],
        "ticks_first": first["ticks"], "ticks_last": last["ticks"], "ticks_pid": last["ticks_pid"], "ticker_alive": last["ticker_alive"],
        "timer_first": first["timer"], "timer_last": last["timer"], "timer_pid": last["timer_pid"],
        "lifespan": last["lifespan"], "threads": last["threads"],
        "gc_enabled": last["gc_enabled"], "gc_freeze_count": last["gc_freeze_count"],
        "redis_ping": last["redis_ping"], "import_redis_ping": last["import_redis_ping"],
        "import_db_count": last["import_db_count"], "db_count": last["db_count"],
        "qlistener_alive": last["qlistener_alive"], "env_marker": last["env_marker"], "backend_port": last["backend_port"],
    })
for r in rows:
    print(json.dumps(r))
pids = [r["pid"] for r in rows]
summary = {
    "workers_seen": len(pids), "errors": errors,
    "distinct_module_random": len({r["module_random"] for r in rows}),
    "distinct_module_uuid": len({r["module_uuid"] for r in rows}),
    "distinct_first_random_now": len({r["first_random_now"] for r in rows}),
    "distinct_first_prng_now": len({r["first_prng_now"] for r in rows}),
    "imported_in_worker": sum(1 for r in rows if r["imported_here"]),
    "ticker_advancing": sum(1 for r in rows if r["ticks_last"] > r["ticks_first"]),
    "ticker_alive": sum(1 for r in rows if r["ticker_alive"]),
    "timer_advancing": sum(1 for r in rows if r["timer_last"] > r["timer_first"]),
    "lifespan_ran_in_worker": sum(1 for r in rows if r["lifespan"]["pid"] == r["pid"]),
    "qlistener_alive": sum(1 for r in rows if r["qlistener_alive"]),
    "start_methods": sorted({str(r["start_method"]) for r in rows}),
}
print("SUMMARY", json.dumps(summary))
if out:
    json.dump({"rows": rows, "summary": summary}, open(out, "w"), indent=1)
