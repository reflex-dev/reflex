"""Group verify_hydration run JSONs by tag and count storms / triggers / crashes. Writes summary.json next to stdout.
Usage: vtable.py OUT_DIR EXPLORER_RESULTS_DIR SUMMARY_JSON"""
import glob
import json
import os
import re
import sys
from collections import defaultdict

out, exp, dest = sys.argv[1:4]
groups = defaultdict(lambda: {"runs": 0, "storm": 0, "crash": 0, "triggered": 0, "storm_when_triggered": 0, "max_win5s": 0,
                              "not_converged": 0, "user_value_lost_in_storage": 0})
for so in sorted(glob.glob(os.path.join(out, "*.stdout"))):
    tag = re.sub(r"_\d+\.stdout$", "", os.path.basename(so))
    js = so[:-7] + ".json"
    g = groups[tag]
    g["runs"] += 1
    if not os.path.exists(js):
        g["crash"] += 1
        continue
    r = json.load(open(js))
    g["storm"] += bool(r.get("storm"))
    g["not_converged"] += not r.get("converged", True)
    g["max_win5s"] = max([g["max_win5s"]] + (r.get("windows_5s") or []))
    click = r.get("click_t") or ((r.get("clicks") or [[None, None]])[0][1])
    if click and "docs" not in tag:
        click = int(click * 1000)
        trig = False
        for t in r.get("per_tab", []):
            boot = [e for e in t.get("log", []) if e[1] == "out" and ("hydrate_and_load" in e[2] or ".hydrate\"" in e[2])]
            hyd = [e for e in t.get("log", []) if e[1] == "in" and 'is_hydrated_rx_state_":true' in e[2]]
            # a tab that read the OLD value for its boot payload and hydrated after the click (vtrigger.py's rule)
            if boot and hyd and boot[0][0] <= click + 300 and hyd[0][0] >= click and 'theme_rx_state_":"green' in boot[0][2]:
                trig = True
        g["triggered"] += trig
        g["storm_when_triggered"] += trig and bool(r.get("storm"))
        if r.get("ls_theme") not in (None, "red") and "pick-red" in json.dumps(r.get("args")) and r.get("storm"):
            g["user_value_lost_in_storage"] += 1
res = {"verify_hydration_runs": groups, "explorer_fixture_reruns": {}}
for f in sorted(glob.glob(os.path.join(exp, "sync", "*.json")) + glob.glob(os.path.join(exp, "stamp", "*.json"))):
    r = json.load(open(f))
    tag = re.sub(r"_\d+\.json$", "", os.path.basename(f))
    e = res["explorer_fixture_reruns"].setdefault(tag, {"runs": 0, "S_storm": 0, "R_revert": 0, "stamp_storm": 0})
    e["runs"] += 1
    if "S" in r:
        e["S_storm"] += (r["S"]["frames_in_quiet_2s"] > 50) or not r["S"]["converged"]
    if "R" in r:
        e["R_revert"] += bool(r["R"]["A_showed_v1_after_change"])
    if "storm" in r:
        e["stamp_storm"] += bool(r["storm"])
json.dump(res, open(dest, "w"), indent=1)
for k, g in sorted(groups.items()):
    print(f"{k:48s} {dict(g)}")
for k, e in sorted(res["explorer_fixture_reruns"].items()):
    print(f"EXPLORER {k:40s} {e}")
