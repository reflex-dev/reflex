"""Print a compact per-repetition timeline from a vdrv.py xtab/stale JSON result.

Usage: python timeline.py <result.json> [rep] [logkey]   (logkey: _full_log | p1_log | p2_log | p3_log | p4_log)
"""
import json
import sys

res = json.load(open(sys.argv[1]))
reps = [int(sys.argv[2])] if len(sys.argv) > 2 and sys.argv[2] != "all" else range(len(res))
key = sys.argv[3] if len(sys.argv) > 3 else "_full_log"
for i in reps:
    r = res[i]
    log = r.get(key) or []
    t0 = r.get("t_logout_click") or (log[0]["t"] if log else 0)
    print(f"=== rep {i} ({key}) logged_out={r.get('tab1_logged_out')} t0={'logout click' if r.get('t_logout_click') else 'first event'}")
    for e in log:
        k = e.get("kind")
        t = e.get("t") or 0
        if key == "_full_log" and t < t0 - 3000:
            continue
        rel = f"{(t - t0) / 1000:+7.2f}s"
        tab = e.get("tab")
        if k == "ws":
            if e.get("dir") == "sent" and e.get("events"):
                print(rel, tab, "SEND", e["events"], e.get("vars") or "")
            elif e.get("dir") == "recv" and (e.get("delta") or e.get("chained")):
                d = e.get("delta") or {}
                d = {kk: vv for kk, vv in d.items() if kk in ("hash", "is_hydrated", "user_sub", "clicks", "has_any_token")}
                ch = [c for c in (e.get("chained") or []) if c]
                if d or ch:
                    print(rel, tab, "RECV", d, ch)
        elif k in ("ls_set", "ls_remove"):
            print(rel, tab, k.upper(), (e.get("value") or "")[:16])
        elif k == "storage_event":
            print(rel, tab, "STORAGE_EVENT", (e.get("old") or "")[:12], "->", (e.get("new") or "")[:12])
        elif k == "cookie_sync":
            print(rel, tab, "COOKIE_SYNC", e.get("status"), e.get("pid") or "")
        elif k == "nav":
            print(rel, tab, "NAV", e.get("to")[:70])
