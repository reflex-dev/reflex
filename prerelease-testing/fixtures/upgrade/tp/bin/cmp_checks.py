"""Compare check-by-check pass/fail of two tpdrive reports. Usage: cmp_checks.py A.json B.json"""
import json, sys
def load(p):
    r = json.load(open(p)); out = {}
    for c in r.get("checks", []):
        out.setdefault(c["name"], []).append(bool(c.get("ok")))
    return out
a, b = load(sys.argv[1]), load(sys.argv[2])
diff = [(n, a.get(n), b.get(n)) for n in dict.fromkeys(list(a) + list(b)) if a.get(n) != b.get(n)]
print(f"checks A={len(a)} B={len(b)} failing A={sum(1 for v in a.values() if not all(v))} B={sum(1 for v in b.values() if not all(v))} differing={len(diff)}")
for d in diff: print("  DIFF", d)
