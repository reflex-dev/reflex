"""Did the user's own (foreground) tab show the OLD value again after the click? Prints tab0's #theme timeline after
the click (ms relative to the click) and the per-tab storage-event counts. Usage: vrevert.py FILE..."""
import json
import sys

for f in sys.argv[1:]:
    r = json.load(open(f))
    click = int((r.get("click_t") or r["clicks"][0][1]) * 1000)
    tl = [(t - click, v) for t, v in r["per_tab"][0]["tl"] if t >= click]
    flips = sum(1 for _, v in tl if v == "green")
    print(f"{f.split('/')[-1]:40s} storm={r.get('storm')!s:5s} tab0 after click: {tl[:8]}{' ...' if len(tl) > 8 else ''} "
          f"old-value-shown={flips}x storage_events={[t['se'] for t in r['per_tab']]}")
