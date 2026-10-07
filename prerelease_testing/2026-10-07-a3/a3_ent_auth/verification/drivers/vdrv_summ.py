"""Summarize vdrv_copy.py stale/away JSON: P3/P4 (stale) and tab1 (away) end states."""
import json
import sys

import playwright  # noqa: F401

assert "/scratchpad/envs/driver/" in playwright.__file__, playwright.__file__

for path in sys.argv[1:]:
    for r in json.load(open(path)):
        if "p3_path" in r or "p3_error" in r:
            print(path.rsplit("/", 1)[1], r["rep"], "P3", r.get("p3_path"), repr(r.get("p3_who")), r.get("p3_path_after_add"), "| P4", r.get("p4_path"), repr(r.get("p4_who")), r.get("p4_path_after_add"), r.get("p3_error", ""))
        else:
            print(path.rsplit("/", 1)[1], r["rep"], "away back_url", r.get("tab1_back_url"), "who", repr(r.get("tab1_who")), "final", r.get("tab1_path_final"), "add", r.get("tab1_add"), r.get("error", ""))
