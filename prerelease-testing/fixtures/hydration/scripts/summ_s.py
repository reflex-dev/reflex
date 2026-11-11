"""Summarise sync_race.py Part S JSONs: summ_s.py <glob-prefix>...  Storm = not converged or >50 frames in the 2 s quiet window."""
import glob, json, sys
for pre in sys.argv[1:]:
    files = sorted(glob.glob(pre + "*.json"), key=lambda f: int(f.rsplit("_", 1)[1].split(".")[0]))
    rows = []
    for f in files:
        d = json.load(open(f)).get("S")
        if not d:
            rows.append(f"   {f.split('/')[-1]}: NO RESULT (driver crash?)"); continue
        storm = (not d["converged"]) or d["frames_in_quiet_2s"] > 50
        rows.append((storm, f"   {f.split('/')[-1]}: storm={storm} frames_total={d['frames_total']} quiet2s={d['frames_in_quiet_2s']} tab_finals={sorted(set(d['finals'].values()))} ls={d['ls_final']} storage_ev_t1={d['storage_events_per_tab'].get('t1')}"))
    n = sum(1 for r in rows if isinstance(r, tuple)); s = sum(1 for r in rows if isinstance(r, tuple) and r[0])
    print(f"{pre.split('/')[-1]}*: storms {s}/{n} (files {len(files)})")
    for r in rows:
        print(r[1] if isinstance(r, tuple) else r)
