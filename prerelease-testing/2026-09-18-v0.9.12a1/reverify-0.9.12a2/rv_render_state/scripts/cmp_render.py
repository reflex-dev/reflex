import json, sys
a = json.load(open(sys.argv[1]))
b = json.load(open(sys.argv[2]))
na, nb = sys.argv[3], sys.argv[4]
def show(d):
    return d
keys = sorted(set(a.get("marks", {})) | set(b.get("marks", {})))
print(f"=== marks: {na} vs {nb} ===")
for k in keys:
    ma = a.get("marks", {}).get(k, {})
    mb = b.get("marks", {}).get(k, {})
    pk = sorted(set(ma) | set(mb))
    diffs = [(p, ma.get(p), mb.get(p)) for p in pk if ma.get(p) != mb.get(p)]
    print(f"{k}: {'SAME' if not diffs else 'DIFF ' + repr(diffs)}")
print(f"=== deltas (computed sections) ===")
for k in sorted(set(a) | set(b)):
    if k in ("marks", "label", "base", "load_seconds", "rows_rebuild_seconds", "ws_frames"):
        continue
    va, vb = a.get(k), b.get(k)
    if va != vb:
        print(f"{k}: {na}={va!r}  {nb}={vb!r}")
    else:
        print(f"{k}: SAME ({va!r})" if not isinstance(va, (dict, list)) or len(str(va)) < 120 else f"{k}: SAME")
