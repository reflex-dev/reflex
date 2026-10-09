"""Compact table of storx.py results. Usage: storx_table.py <label>..."""
import json
import sys
from pathlib import Path

L = Path(__file__).resolve().parent.parent / "logs"
for lb in sys.argv[1:]:
    for r in json.loads((L / f"{lb}-storx.json").read_text()):
        print(f"=== {lb} rep{r['rep']} error={r.get('error')}")
        for name, d in r["steps"].items():
            w = [(t, k, (v or "").split(";")[0].replace("vx_ck=", "")) for t, k, v in d["writes"]]
            print(f"  {name:52s} who={str(d['who']):6s} shown={d['shown_draft']!r:18} ls={d['ls_draft']!r:18} ck={d['cookie_ck']!r:14} writes={w}"[:300])
