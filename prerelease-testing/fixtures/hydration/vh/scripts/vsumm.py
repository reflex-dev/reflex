"""Summarise vh_tabs.py result JSONs: one line per run. Usage: vsumm.py FILE...  (run with the driver venv python)"""
import json
import sys

for f in sys.argv[1:]:
    try:
        r = json.load(open(f))
    except Exception as e:
        print(f, "UNREADABLE", e)
        continue
    a = r.get("args", {})
    key = "doc_final" if str(a.get("scenario")).startswith("docs") else "theme_final"
    finals = r.get(key) or []
    clicks = r.get("clicks") or []
    slow = [c for c in clicks if not isinstance(c[2], (int, float)) or c[2] > 1.0]
    print(f"{f.split('/')[-1]:40s} storm={r.get('storm')!s:5s} win5s={r.get('windows_5s')} conv={r.get('converged')!s:5s} "
          f"distinct_finals={sorted(set(finals))} ls={r.get('ls_doc' if key == 'doc_final' else 'ls_theme')} "
          f"clicks={len(clicks)} slow_or_failed={len(slow)} heal={r.get('heal_windows_5s')} heal_conv={r.get('heal_converged')} "
          f"vis={''.join(v[0] for v in r.get('visibility') or [])} uvi={[t.get('uvi') for t in r.get('per_tab', [])]}")
