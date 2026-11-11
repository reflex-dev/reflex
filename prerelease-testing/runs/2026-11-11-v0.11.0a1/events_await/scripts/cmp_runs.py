"""Compare two drive_await.py result files: print cases whose visible outcome differs."""
import json, sys, re
a, b = (json.load(open(p))["results"] for p in sys.argv[1:3])
def norm(r):
    s = dict(r.get("snapshot") or {})
    res = s.get("result") or ""
    res = re.sub(r"0x[0-9a-f]+", "0x", res)
    res = re.sub(r"depth=\d+", "depth=N", res) if "RecursionError" in res else res
    s["result"] = res
    if "RecursionError" in res: s["depth"] = "N"
    return {"completed": r.get("completed"), "snap": s, "toasts": sorted(r.get("toasts") or []), "hist": r.get("result_history"),
            "progress": (r.get("ws") or {}).get("progress_values"), "ping_ok": isinstance(r.get("ping_after_s"), float) if "ping_after_s" in r else None}
same = diff = 0
for k in a:
    if k not in b: print("MISSING in B:", k); continue
    na, nb = norm(a[k]), norm(b[k])
    if na == nb: same += 1; continue
    diff += 1
    print("DIFF", k)
    for f in na:
        if na[f] != nb[f]:
            if f == "snap":
                for x in na[f]:
                    if na[f][x] != nb[f].get(x): print(f"   {x}: A={na[f][x]!r}\n   {' '*len(x)}  B={nb[f].get(x)!r}")
            else: print(f"   {f}: A={na[f]!r} B={nb[f]!r}")
print(f"same={same} diff={diff}")
for name, r in (("A", a), ("B", b)):
    slow = {k: v.get("ping_after_s") for k, v in r.items() if not isinstance(v.get("ping_after_s"), float) or v["ping_after_s"] > 1}
    print(name, "slow/failed pings:", slow)
