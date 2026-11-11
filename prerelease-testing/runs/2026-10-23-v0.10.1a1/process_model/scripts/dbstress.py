"""dbstress.py <base_url> [threads=24] [per_thread=12]: concurrent /api/dbwrite across workers (sqlite engine
inherited through fork). Reports errors by type, per-worker counts, final db_count vs expected."""

import json
import sys
import threading
import urllib.error
import urllib.request

base = sys.argv[1].rstrip("/")
T = int(sys.argv[2]) if len(sys.argv) > 2 else 24
P = int(sys.argv[3]) if len(sys.argv) > 3 else 12
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
lock = threading.Lock()
res = {"ok": 0, "errors": {}, "pids": {}, "max_count": 0, "err_samples": []}


def worker():
    for _ in range(P):
        try:
            with opener.open(f"{base}/api/dbwrite", timeout=30) as r:
                d = json.load(r)
            with lock:
                res["ok"] += 1
                res["pids"][d["pid"]] = res["pids"].get(d["pid"], 0) + 1
                res["max_count"] = max(res["max_count"], d["db_count"])
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:200]
            try:
                err = json.loads(body).get("error", body)
            except Exception:  # noqa: BLE001
                err = f"HTTP {e.code} {body}"
            key = err.split(":")[0]
            with lock:
                res["errors"][key] = res["errors"].get(key, 0) + 1
                if len(res["err_samples"]) < 5:
                    res["err_samples"].append(err)
        except Exception as e:  # noqa: BLE001
            with lock:
                res["errors"][type(e).__name__] = res["errors"].get(type(e).__name__, 0) + 1
                if len(res["err_samples"]) < 5:
                    res["err_samples"].append(str(e)[:200])


ths = [threading.Thread(target=worker) for _ in range(T)]
[t.start() for t in ths]
[t.join() for t in ths]
with opener.open(f"{base}/api/whoami", timeout=10) as r:
    final = json.load(r)["db_count"]
res["final_db_count"] = final
res["expected"] = T * P
print(json.dumps(res))
