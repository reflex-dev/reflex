"""Summarize drive_legacy.py fail-page results: one line per scenario, for side-by-side comparison."""
import json, sys, re
for path in sys.argv[1:]:
    d = json.load(open(path))["results"]
    print("==", path.split("/")[-1])
    for k, r in d.items():
        if not k.startswith("fail:"): continue
        c = {x: v for x, v in (r["client_before_ping"] or {}).items() if v not in ("", "0", None) and x not in ("result", "other-n")}
        log = " ".join(r["log"].split())
        errs = sorted(set(re.findall(r"((?:TypeError|ValueError|RuntimeError|KeyError|CancelledError|LockExpired\w*|StateSchema\w*|Timeout\w*)[^\n]{0,90})", log)))
        firsts = {x: v[0][0] for x, v in r["hist_ms"].items() if x not in ("result",)}
        print(f"  {k[5:]:28s} ping={r['ping_latency_s']} 2nd={r.get('second_ping_s','-')} client={c}")
        print(f"  {'':28s} server={r['server_view']}")
        print(f"  {'':28s} first-seen-ms={firsts} blocked={r.get('blocked','-')} errs={[e[:100] for e in errs][:3]}")
        if "client_0_5s_after_cancel" in r:
            s1 = {x: v for x, v in r["client_0_5s_after_cancel"].items() if v not in ("", "0", None) and x not in ("result", "other-n")}
            print(f"  {'':28s} 0.5s-after-cancel={s1} hist={ {x: v for x, v in r['hist_ms'].items() if x in ('c','partial','count','status')} }")
