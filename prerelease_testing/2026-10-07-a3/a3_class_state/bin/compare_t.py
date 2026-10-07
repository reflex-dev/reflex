"""Side-by-side t1/t2 matrix tables for any set of labels: compare_t.py <outdir> <label>...  (reads t1_matrix.<label>.json, t2_matrix.<label>.json)."""
import collections, json, sys
d, labels = sys.argv[1], sys.argv[2:]
def c1(r):
    if "setup_error" in r: return "SETUP-ERR"
    s = []
    if r["patch_error"]: s.append("PATCH-ERR(" + r["patch_error"].split(":")[0] + ")")
    if r.get("undo_error"): s.append("UNDO-ERR(" + r["undo_error"].split(":")[0] + ")")
    if r["leaked"]: s.append("LEAK")
    if not s: s.append("clean")
    s.append("vis" if r["patch_visible_to_instances"] else "invis")
    return ",".join(s)
t1 = {k: json.load(open(f"{d}/t1_matrix.{k}.json"))["matrix"] for k in labels}
print("== t1 per-mechanism counts (undo/patch error kinds / leaked kinds / visible-to-instances kinds)")
mechs = list(dict.fromkeys(r["mech"] for r in t1[labels[0]]))
for m in mechs:
    cells = []
    for k in labels:
        rows = [r for r in t1[k] if r["mech"] == m and "setup_error" not in r]
        e = sum(1 for r in rows if r["patch_error"] or r.get("undo_error")); l = sum(1 for r in rows if r["leaked"]); v = sum(1 for r in rows if r["patch_visible_to_instances"])
        cells.append(f"{e}/{l}/{v} of {len(rows)}")
    print(f"{m[:60]:<60} " + " | ".join(f"{k}:{c:<14}" for k, c in zip(labels, cells)))
print()
print(f"{'kind':<52} {'mechanism':<48} " + " | ".join(f"{k:<34}" for k in labels))
for i, r in enumerate(t1[labels[0]]):
    print(f"{r['kind'][:52]:<52} {r['mech'][:48]:<48} " + " | ".join(f"{c1(t1[k][i]):<34}" for k in labels))
try:
    t2 = {k: json.load(open(f"{d}/t2_matrix.{k}.json"))["rows"] for k in labels}
except FileNotFoundError:
    sys.exit(0)
print("\n== t2 totals")
for k in labels:
    rows = t2[k]
    print(f"  {k:<10} raises={sum(1 for r in rows if r.get('error'))} ok={sum(1 for r in rows if not r.get('error'))} ran_user_code={sum(1 for r in rows if r.get('side_effects'))} of {len(rows)}")
