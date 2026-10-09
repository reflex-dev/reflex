"""Compare hunt.py results across builds. Usage: hunt_cmp.py <label> [<label>...]   (reads ../logs/<label>-hunt-*.json)"""
import json
import sys
from pathlib import Path

L = Path(__file__).resolve().parent.parent / "logs"
labels = sys.argv[1:]


def load(label, mode):
    f = L / f"{label}-hunt-{mode}.json"
    return json.loads(f.read_text()) if f.exists() else []


print("## fresh anonymous browser (per rep): hash writes / app storage writes / cookies / cookie syncs / sent events")
for lb in labels:
    for r in load(lb, "fresh"):
        app_writes = sorted({(w["store"] if w["kind"] != "w_cookie" else "cookie", w["key"]) for w in r.get("writes", []) if w["key"] not in ("token", "react-router-scroll-positions")})
        print(f"{lb} rep{r['rep']}: hash_writes={r.get('hash_writes')} app_writes={app_writes} ls={list((r.get('localStorage') or {}).keys())} cookies={r.get('context_cookies')} totals={r.get('totals')}")
print()
print("## signed-in page loads: per step counts")
for lb in labels:
    for r in load(lb, "loads"):
        print(f"{lb} rep{r['rep']} login={r.get('login')} error={r.get('error')}")
        for name, s in (r.get("steps") or {}).items():
            c = {k: v for k, v in s.items() if not k.endswith(("_who", "_path"))}
            who = {k: v for k, v in s.items() if k.endswith("_who")}
            print(f"   {name:28s} {c}  {who}")
        print(f"   totals {r.get('totals')} entries={r.get('entries')}")
print()
print("## relogin")
for lb in labels:
    for r in load(lb, "relogin"):
        print(f"{lb} rep{r['rep']} ok={r.get('ok')} bob_view={r.get('bob_view')} bob_entries={r.get('bob_entries')} newtab={r.get('newtab')} totals={r.get('totals')}")
print()
print("## pubslash (anonymous direct loads)")
for lb in labels:
    for r in load(lb, "pubslash"):
        print(f"{lb}: " + "; ".join(f"{p} -> {v.get('final')} pid={v.get('pid_text')} chained={v.get('chained')}" for p, v in (r.get('loads') or {}).items()))
