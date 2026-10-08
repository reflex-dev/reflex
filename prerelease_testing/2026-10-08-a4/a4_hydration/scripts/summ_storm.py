import json, sys
for line in sys.stdin:
    if line.startswith("S:"):
        try:
            d = json.loads(line[3:])
        except Exception:
            print(line[:200]); continue
        print("S conv=%s quiet=%s frames=%s finals=%s se_t1=%s" % (d["converged"], d["frames_in_quiet_2s"], d["frames_total"], sorted(set(d["finals"].values())), d["storage_events_per_tab"]["t1"]))
    else:
        print(line.strip()[:300])
