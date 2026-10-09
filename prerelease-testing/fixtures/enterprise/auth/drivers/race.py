"""Per repetition: did the cross-tab race happen (tab1 re-wrote the old hash after tab2's logout),
and how was it resolved? Usage: python race.py <xtab.json>..."""
import json
import sys

for f in sys.argv[1:]:
    res = json.load(open(f))
    print("==", f.rsplit("/", 1)[-1])
    for r in res:
        t0 = r.get("t_logout_click") or 0
        log = [e for e in r.get("_full_log", []) if (e.get("t") or 0) >= t0]
        stale_rewrite = [e for e in log if e.get("tab") == "tab1" and e.get("kind") == "ls_set" and e.get("value")]
        empty_writes = [e for e in log if e.get("kind") == "ls_set" and e.get("value") == ""]
        tab2_recon = any(e.get("tab") == "tab2" and e.get("kind") == "ws" and e.get("dir") == "sent" and "reconcile_tokens_after_sync" in (e.get("events") or []) for e in log)
        print(f"rep {r['rep']}: race(tab1 re-wrote old hash)={bool(stale_rewrite)} empty-hash writes={[(e['tab'], round((e['t']-t0)/1000,2)) for e in empty_writes]} tab2 sent reconcile={tab2_recon} -> tab1_logged_out={r.get('tab1_logged_out')}")
