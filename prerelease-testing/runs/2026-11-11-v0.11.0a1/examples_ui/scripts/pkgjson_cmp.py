"""pkgjson_cmp.py <a.json> <b.json>: semantic diff of two .web/package.json files (ignores formatting)."""
import json, sys
a, b = (json.load(open(p)) for p in sys.argv[1:3])
def flat(d, pre=""):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(flat(v, pre + k + "."))
        else:
            out[pre + k] = v
    return out
fa, fb = flat(a), flat(b)
ch = [f"{k}: {fa.get(k)!r} -> {fb.get(k)!r}" for k in sorted(set(fa) | set(fb)) if fa.get(k) != fb.get(k)]
print("semantic package.json diff:", "; ".join(ch) if ch else "IDENTICAL (formatting only)" if open(sys.argv[1]).read() != open(sys.argv[2]).read() else "IDENTICAL")
