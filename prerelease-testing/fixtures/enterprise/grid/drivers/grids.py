"""Print per-grid content (headers, badges, memo badges, tooltip texts, pinned/group rows, .cheap cells, row texts) of entr runs.

Usage: $SB/envs/driver/bin/python drivers/grids.py out/<run> [scenario-prefix ...]
"""

import json
import sys
from pathlib import Path

assert ("/envs/" + __import__("os").environ.get("DRV_VENV", "driver") + "/") in sys.executable, sys.executable
run = Path(sys.argv[1])
prefixes = sys.argv[2:] or ["r1_", "r2_", "r2c", "r3_", "r4_"]
for f in sorted(run.glob("*.json")):
    if not any(f.name.startswith(p) for p in prefixes):
        continue
    d = json.loads(f.read_text())
    print(f"== {f.stem}")
    for k, v in d["measure_plus4s"]["grids"].items():
        print(f"  {k}: headers={v['headers']} cells={v['cells']} badges={v.get('badges')} memo={v.get('memo_badges')} tip={v.get('tip_texts')} "
              f"pinned={v.get('pinned_top_rows')} group={v.get('group_rows')} cheap={v.get('cheap_cells')}")
        for t in v.get("row_texts", [])[:3]:
            print(f"      {t[:220]}")
    if "detail" in d:
        for k, v in d["detail"].items():
            print(f"  detail {k}: {v}")
