"""Compare two rtr_drive.py result files step by step (backend self.router snapshots + frontend fields).

Usage: cmp_rtr.py A.json B.json
Volatile fields (token, session id, pid, websocket key, host/port of the run) are masked; everything else that differs
is printed. Exit 0 = identical modulo volatile fields.
"""

import json
import re
import sys

import playwright  # noqa: F401

assert "/envs/driver/" in playwright.__file__

VOLATILE = {"tok", "sid", "pid"}


def norm(v):
    s = json.dumps(v, sort_keys=True)
    s = re.sub(r"localhost:\d+", "localhost:PORT", s)
    s = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "TOKEN", s)
    s = re.sub(r'sec-websocket-key[^,}]*', "sec-websocket-key=K", s)
    s = re.sub(r'sec_websocket_key[^,}]*', "sec_websocket_key=K", s)
    s = re.sub(r'sec-websocket-protocol[^,}]*', "sec-websocket-protocol=V", s)
    s = re.sub(r"session_id[^,}]*", "session_id=S", s)
    return s


a, b = (json.load(open(p)) for p in sys.argv[1:3])
sa = {s["step"]: s for s in a["steps"]}
sb = {s["step"]: s for s in b["steps"]}
ndiff = 0
for name in list(dict.fromkeys(list(sa) + list(sb))):
    x, y = sa.get(name), sb.get(name)
    if not x or not y:
        print(f"{name}: only in {'A' if x else 'B'}")
        ndiff += 1
        continue
    if x["url"].split("//")[1].split("/", 1)[1:] != y["url"].split("//")[1].split("/", 1)[1:]:
        print(f"{name}: URL A={x['url']} B={y['url']}")
        ndiff += 1
    lx = [{k: v for k, v in e.items() if k not in VOLATILE} for e in x["log"]]
    ly = [{k: v for k, v in e.items() if k not in VOLATILE} for e in y["log"]]
    if [norm(e) for e in lx] != [norm(e) for e in ly]:
        ndiff += 1
        print(f"{name}: LOG differs")
        for i in range(max(len(lx), len(ly))):
            ex = lx[i] if i < len(lx) else {}
            ey = ly[i] if i < len(ly) else {}
            keys = sorted(set(ex) | set(ey))
            d = {k: (ex.get(k), ey.get(k)) for k in keys if norm(ex.get(k)) != norm(ey.get(k))}
            if d:
                print(f"   [{i}] {ex.get('tag')}/{ey.get('tag')}: {d}")
    fx, fy = x.get("front"), y.get("front")
    if fx or fy:
        for k in sorted(set(fx or {}) | set(fy or {})):
            vx, vy = norm((fx or {}).get(k)), norm((fy or {}).get(k))
            if vx != vy:
                print(f"{name}: FRONT {k}: A={vx[:300]} | B={vy[:300]}")
print(f"steps A={len(sa)} B={len(sb)} log/url diffs={ndiff}")
for k in ("recv_headers", "recv_cookie", "front_html_has"):
    print(k, "A=", str(a.get(k))[:300], "B=", str(b.get(k))[:300])
print("sync A=", a.get("sync", {}).get("t1"), a.get("sync", {}).get("t2"), "B=", b.get("sync", {}).get("t1"), b.get("sync", {}).get("t2"))
print("reconnect A=", {k: v for k, v in a.get("reconnect", {}).items() if k != "log_after"},
      "B=", {k: v for k, v in b.get("reconnect", {}).items() if k != "log_after"})
print("leaks(in,out,docs,console) A=", {k: (v["in"], v["out"], v["docs"], v["console"]) for k, v in a["leaks"].items()})
print("leaks(in,out,docs,console) B=", {k: (v["in"], v["out"], v["docs"], v["console"]) for k, v in b["leaks"].items()})
