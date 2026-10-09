"""Compare hyd_driver scenario results between runs: prints fields whose values differ.
Usage: cmp_hyd.py <dirA> <dirB> [<dirC>] [--full]"""
import json
import sys
from pathlib import Path

dirs = [Path(a) for a in sys.argv[1:] if not a.startswith("--")]
full = "--full" in sys.argv
SKIP_SUB = ("frames", "timeline", "duration", "screenshot", "anomalies", "token", "uuid", "stamp", "raw", "created", "pid", "session_id", "url")
SKIP_END = ("_ms", "_s", ".tb")


def skipped(k: str) -> bool:
    kl = k.lower()
    if any(s in kl for s in SKIP_SUB) or any(seg.endswith(SKIP_END) for seg in kl.split(".")):
        return True
    return any(seg.startswith(("t_", "time")) for seg in kl.split("."))


def flat(d, pre=""):
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            out.update(flat(v, f"{pre}.{k}" if pre else str(k)))
    elif isinstance(d, list) and d and all(isinstance(x, (dict, list)) for x in d) and len(d) < 30:
        for i, v in enumerate(d):
            out.update(flat(v, f"{pre}[{i}]"))
    else:
        out[pre] = d
    return out


names = sorted({p.stem for d in dirs for p in d.glob("s*.json") if not p.stem.endswith(".raw")}, key=lambda s: (len(s), s))
for n in names:
    data = []
    for d in dirs:
        f = d / f"{n}.json"
        data.append(flat(json.loads(f.read_text())) if f.exists() else None)
    if any(x is None for x in data):
        print(f"## {n}: missing in {[str(d) for d, x in zip(dirs, data) if x is None]}")
        continue
    keys = sorted(set().union(*[set(x) for x in data]))
    diffs = []
    for k in keys:
        if not full and skipped(k):
            continue
        vals = [x.get(k, "<absent>") for x in data]
        if any(json.dumps(v, default=str) != json.dumps(vals[0], default=str) for v in vals[1:]):
            diffs.append((k, vals))
    print(f"## {n}: status={[x.get('status') for x in data]} ndiff={len(diffs)}")
    for k, vals in diffs[:40]:
        print(f"   {k}: " + " | ".join(json.dumps(v, default=str)[:160] for v in vals))
