"""Side-by-side summary of t1_matrix JSON outputs (a2 / a1 / 0.9.12)."""
import json, sys
vers = [("a2", "0.10.0a2"), ("a1", "0.10.0a1"), ("s0912", "0.9.12")]
data = {k: json.load(open(f"{sys.argv[1]}/t1_matrix.{k}.json")) for k, _ in vers}
def cell(r):
    if "setup_error" in r:
        return "SETUP-ERR"
    s = []
    if r["patch_error"]:
        s.append("PATCH-ERR(" + r["patch_error"].split(":")[0] + ")")
    if r.get("undo_error"):
        s.append("UNDO-ERR(" + r["undo_error"].split(":")[0] + ")")
    if r["leaked"]:
        s.append("LEAK")
    if not s:
        s.append("clean")
    s.append("vis" if r["patch_visible_to_instances"] else "invis")
    return ",".join(s)
rows0 = data["a2"]["matrix"]
print(f"{'kind':<58} {'mechanism':<52} " + " | ".join(f"{v:<38}" for _, v in vers))
for i, r in enumerate(rows0):
    cells = [cell(data[k]["matrix"][i]) for k, _ in vers]
    print(f"{r['kind'][:58]:<58} {r['mech'][:52]:<52} " + " | ".join(f"{c:<38}" for c in cells))
