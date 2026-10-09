"""Compare driver run JSONs under explicit labels (so the same tag from two campaigns can sit side by side).

Usage: compare_sets.py label=path.json label=path.json ...  (first = reference)
Prints check totals, per-check status differences vs the first run, and console error/warning signature matrix.
"""
import json
import re
import sys
from pathlib import Path

assert "/envs/" in sys.executable, sys.executable
sys.path.insert(0, str(Path(__file__).parent))
from harness import is_benign_console  # noqa: E402


def sig(m):
    t = re.sub(r"\?v=[0-9a-f]+|:\d+:\d+|token=[0-9a-f-]+|\d{1,2}:\d{2}:\d{2}|\d{4}-\d\d-\d\dT[\d:.]+Z", "", m["text"])
    return f'{m["type"]}: {t[:90]}'.replace("\n", " ")


runs = {}
for arg in sys.argv[1:]:
    label, _, f = arg.partition("=")
    runs[label] = json.load(open(f))
for label, d in runs.items():
    st = {}
    for r in d["results"]:
        st[r["status"]] = st.get(r["status"], 0) + 1
    print(f"{label:22} checks={st} console={len(d['console'])} page_errors={len(d['page_errors'])} bad_req={len(d['bad_requests'])} ws_frames={len(d.get('ws_frames', d.get('ws', [])))}")
sigs = {t: {sig(m) for m in d["console"] if m["type"] in ("error", "warning") and not is_benign_console(m["text"])} for t, d in runs.items()}
allsig = sorted(set().union(*sigs.values()))
for s in allsig:
    print("  ", " ".join("X" if s in sigs[t] else "." for t in runs), s)
names = list(runs)
for t in names[1:]:
    a = {r["name"]: r["status"] for r in runs[names[0]]["results"]}
    b = {r["name"]: r["status"] for r in runs[t]["results"]}
    diff = {k: (a.get(k), b.get(k)) for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)}
    print(f"check-status differences {names[0]} -> {t}: {json.dumps(diff, indent=1) if diff else 'none'}")
