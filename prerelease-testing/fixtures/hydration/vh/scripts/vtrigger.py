"""For each run JSON (vh_tabs.py or vh_rawcdp.py), list the tabs that were booting across the user's click: their
CONNECT/hydrate was sent before the click's delta arrived and they hydrated after the click. Shows the value the tab
read at boot and whether its final boot delta carried the theme (the #7493 echo). Usage: vtrigger.py FILE..."""
import json
import sys

for f in sys.argv[1:]:
    r = json.load(open(f))
    if "click_t" in r:
        click = int(r["click_t"] * 1000)
    elif r.get("clicks"):
        click = int(r["clicks"][0][1] * 1000)
    else:
        continue
    out = []
    for i, t in enumerate(r["per_tab"]):
        boot = [e for e in t["log"] if e[1] == "out" and ("hydrate_and_load" in e[2] or ".hydrate\"" in e[2] or "update_vars_internal" in e[2] and "last_doc" in e[2])]
        if not boot:
            continue
        ct = boot[0][0]
        val = "green" if 'theme_rx_state_":"green' in boot[0][2] else ("red" if 'theme_rx_state_":"red' in boot[0][2] else "?")
        h = [e for e in t["log"] if e[1] == "in" and 'is_hydrated_rx_state_":true' in e[2]]
        ht = h[0][0] if h else None
        echo = None
        if h:
            echo = "theme=green" if 'theme_rx_state_":"green' in h[0][2] else ("theme=red" if 'theme_rx_state_":"red' in h[0][2] else "no-theme")
        if ct <= click + 300 and ht is not None and ht >= click:
            out.append(f"tab{i}: boot-send@{ct - click:+d}ms read={val} hydrated@{ht - click:+d}ms hydrated-delta:{echo}")
    print(f"{f.split('/')[-1]:45s} storm={r.get('storm')!s:5s} booting-across-click: {out or 'none'}")
