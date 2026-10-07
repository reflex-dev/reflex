"""Summarize t2_matrix JSON outputs across versions (a2 / a1 / 0.9.12)."""
import json, sys, collections
vers = [("a2", "0.10.0a2"), ("a1", "0.10.0a1"), ("s0912", "0.9.12")]
data = {k: json.load(open(f"{sys.argv[1]}/t2_matrix.{k}.json"))["rows"] for k, _ in vers}
n = len(data["a2"])
assert all(len(v) == n for v in data.values())
def cell(r):
    if "decl_error" in r or "value_error" in r:
        return "SETUP-ERR"
    se = ",".join(f"{k.split('.')[0]}x{v}" for k, v in r["side_effects"].items())
    if r["error"]:
        return "RAISES" + (f" [{se}]" if se else "")
    return f"ok->{str(r['after_inst'])[:14]}" + (f" [{se}]" if se else "")
# aggregate
agg = {k: collections.Counter() for k, _ in vers}
for k, _ in vers:
    for r in data[k]:
        agg[k]["raises" if r.get("error") else "ok"] += 1
        if r.get("side_effects"):
            agg[k]["with_side_effects"] += 1
print("totals over", n, "(declaration, value) pairs:")
for k, v in vers:
    print(f"  {v:<9} raises={agg[k]['raises']:<4} ok={agg[k]['ok']:<4} assignments that ran user code={agg[k]['with_side_effects']}")
print()
want = [l for l in sys.argv[2:]] or None
print(f"{'declaration':<48} {'assigned value':<44} " + " | ".join(f"{v:<26}" for _, v in vers))
for i in range(n):
    r = data["a2"][i]
    if want and not any(w in r["decl"] for w in want):
        continue
    print(f"{r['decl'][:48]:<48} {r['value'][:44]:<44} " + " | ".join(f"{cell(data[k][i]):<26}" for k, _ in vers))
