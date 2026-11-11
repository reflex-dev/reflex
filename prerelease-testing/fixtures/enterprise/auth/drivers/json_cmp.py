"""Structural diff of two JSON result files (ignores pids, timings, tokens, ids). Usage: json_cmp.py <a.json> <b.json>"""
import json
import re
import sys

VOLATILE = re.compile(r"(pid|elapsed|latency|duration|_s$|token|code|client_id|secret$|session|state$|verifier|challenge|exp|iat|jti|date|retry|url|id$|ticket|nonce|hash)", re.I)


def norm(v):
    if isinstance(v, str):
        v = re.sub(r"pid-\d+", "pid-N", v)
        v = re.sub(r"\d+ second", "N second", v)
        v = re.sub(r"[0-9a-f]{16,}", "HEX", v)
        v = re.sub(r"[A-Za-z0-9_\-]{30,}", "TOK", v)
    return v


def walk(a, b, path=""):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            p = f"{path}.{k}"
            if VOLATILE.search(str(k)):
                if (k in a) != (k in b):
                    print(f"KEY {p}: only in {'A' if k in a else 'B'}")
                continue
            if k not in a or k not in b:
                print(f"KEY {p}: only in {'A' if k in a else 'B'}")
                continue
            walk(a[k], b[k], p)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            print(f"LEN {path}: {len(a)} vs {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            walk(x, y, f"{path}[{i}]")
    else:
        if norm(a) != norm(b):
            print(f"VAL {path}: {str(a)[:150]!r} vs {str(b)[:150]!r}")


walk(json.load(open(sys.argv[1])), json.load(open(sys.argv[2])))
