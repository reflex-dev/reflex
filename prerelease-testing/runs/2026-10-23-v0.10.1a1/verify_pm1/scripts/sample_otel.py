"""sample_otel.py <base> [n] [--json out]: hit /api/otelstat n times, sleep 2 s, hit again; aggregate per pid."""
import json, sys, time, urllib.request
base = sys.argv[1].rstrip("/"); n = int(sys.argv[2]) if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else 40
out = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
def hit():
    with opener.open(f"{base}/api/otelstat", timeout=5) as r: return json.load(r)
first = {}
for _ in range(n):
    d = hit(); first.setdefault(d["pid"], d)
time.sleep(2.5)
last = {}
for _ in range(n):
    d = hit(); last[d["pid"]] = d
rows = []
for pid in sorted(last):
    a, b = first.get(pid, last[pid]), last[pid]
    rows.append({"pid": pid, "imported_here": b["imported_in_this_process"], "threads": b["threads"],
        "spans_exported_here_first": a["spans_exported_here"], "spans_exported_here_last": b["spans_exported_here"],
        "metrics_exported_here_last": b["metrics_exported_here"], "sched_running": b["sched_running"],
        "sched_thread_alive": b["sched_thread_alive"], "job_runs_first": a["job_runs"], "job_runs_last": b["job_runs"],
        "job_pid": b["job_pid"], "qlistener_alive": b["qlistener_alive"], "queue_depth": b["queue_depth"]})
for r in rows: print(json.dumps(r))
s = {"workers_seen": len(rows), "imported_in_worker": sum(r["imported_here"] for r in rows),
     "spans_exported_in_worker": sum(r["spans_exported_here_last"] > 0 for r in rows),
     "metrics_exported_in_worker": sum(r["metrics_exported_here_last"] > 0 for r in rows),
     "sched_running_flag": sum(r["sched_running"] for r in rows), "sched_thread_alive": sum(r["sched_thread_alive"] for r in rows),
     "job_advancing": sum(r["job_runs_last"] > r["job_runs_first"] for r in rows),
     "qlistener_alive": sum(r["qlistener_alive"] for r in rows), "max_queue_depth": max(r["queue_depth"] for r in rows)}
print("SUMMARY", json.dumps(s))
if out: json.dump({"rows": rows, "summary": s}, open(out, "w"), indent=1)
