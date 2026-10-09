"""Print the key fields of drive_mini.py reports side by side. Usage: mini_summary.py REPORT.json [...]"""
import json
import sys

KEYS = ("partial_visible_with_error", "partial_visible_after_next_event", "partial_persisted_after_reload",
        "client_server_diverged", "load_note_before_ping", "load_note_after_ping", "final", "after_b",
        "after_next_event", "after_reload", "routes_with_page_errors")
for p in sys.argv[1:]:
    r = json.load(open(p))
    print("=====", r["label"])
    for x in r["results"]:
        d = x["details"]
        keep = {k: d[k] for k in KEYS if isinstance(d, dict) and k in d}
        if "ui_after_reload" in d:
            keep["ui_after_reload"] = {k: v for k, v in d["ui_after_reload"].items() if k in ("status", "items")}
        print(f"[{x['status']:7}] {x['name']}: {json.dumps(keep)}")
