"""Compare console-message signatures and check outcomes between run JSONs (base vs up vs cold).

Usage: compare_runs.py <json> <json> [...]  (prints per-run check summary + console signature diff)
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from harness import is_benign_console  # noqa: E402


def sig(m):
    t = re.sub(r"\?v=[0-9a-f]+|:\d+:\d+|token=[0-9a-f-]+|\d{1,2}:\d{2}:\d{2}", "", m["text"])
    return f'{m["type"]}: {t[:90]}'.replace("\n", " ")


runs = {}
for f in sys.argv[1:]:
    d = json.load(open(f))
    runs[d["tag"]] = d
    st = {}
    for r in d["results"]:
        st[r["status"]] = st.get(r["status"], 0) + 1
    print(f"{d['tag']:24} checks={st} console={len(d['console'])} page_errors={len(d['page_errors'])} bad_req={len(d['bad_requests'])}")
sigs = {t: {sig(m) for m in d["console"] if m["type"] in ("error", "warning") and not is_benign_console(m["text"])} for t, d in runs.items()}
allsig = set().union(*sigs.values())
for s in sorted(allsig):
    print("  ", " ".join("X" if s in sigs[t] else "." for t in runs), s)
names = list(runs)
for t in names[1:]:
    a = {r["name"]: r["status"] for r in runs[names[0]]["results"]}
    b = {r["name"]: r["status"] for r in runs[t]["results"]}
    diff = {k: (a.get(k), b.get(k)) for k in set(a) | set(b) if a.get(k) != b.get(k)}
    print(f"check-status differences {names[0]} -> {t}: {diff if diff else 'none'}")
