"""Summarise f6_natural.py output lines ("<label> {json}") read from stdin; other lines pass through."""
import json
import sys

for line in sys.stdin:
    lab, _, js = line.partition(" ")
    try:
        r = json.loads(js)
        r["click_delay_ms"]
    except (ValueError, KeyError, TypeError):
        print(line, end="")
        continue
    print(lab, 'cd=%s run=%s interactive=%s ws_open=%s click=%s connect=%s IN_WINDOW=%s boot=%s trace=%s' % (
        r['click_delay_ms'], r['run'], r['t_interactive'], r['t_ws_open'], r['t_click'], r['t_connect_sent'],
        r['connect_after_click'], r['boot_router_pathname'], r['trace']) + ' final=' + str(r.get('final_path')), flush=True)
