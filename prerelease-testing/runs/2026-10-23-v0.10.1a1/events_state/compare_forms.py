"""Diff the per-form handler records of two drive_forms.py runs (prev vs new)."""
import json, sys
a = json.load(open(sys.argv[1])); b = json.load(open(sys.argv[2]))
pa = a["pages"]["/legacy"]; pb = b["pages"]["/legacy"]
for key in pa:
    ra = pa[key].get("results", {}); rb = pb.get(key, {}).get("results", {})
    for k in sorted(set(ra) | set(rb)):
        da = ra.get(k, {}).get("data"); db = rb.get(k, {}).get("data")
        ta = ra.get(k, {}).get("type"); tb = rb.get(k, {}).get("type")
        if da == db and ta == tb:
            print(f"SAME     {k:18} {ta} {json.dumps(da)[:160]}")
        else:
            print(f"DIFF     {k:18}\n   prev {ta}: {json.dumps(da)[:400]}\n   new  {tb}: {json.dumps(db)[:400]}")
            if isinstance(da, dict) and isinstance(db, dict):
                for kk in sorted(set(da) | set(db)):
                    if da.get(kk, "<absent>") != db.get(kk, "<absent>"):
                        print(f"      key {kk!r}: prev={da.get(kk, '<absent>')!r} new={db.get(kk, '<absent>')!r}")
                if list(da) != list(db) and set(da) == set(db):
                    print(f"      key ORDER differs: prev={list(da)} new={list(db)}")
    if pa[key].get("error") or pb.get(key, {}).get("error"):
        print("   ERRORS:", pa[key].get("error"), "|", pb.get(key, {}).get("error"))
    if "after_reset" in pa[key]:
        print("   after_reset prev", pa[key]["after_reset"], "new", pb[key].get("after_reset"))
print("pageerrors prev", a["errors"], "new", b["errors"])
