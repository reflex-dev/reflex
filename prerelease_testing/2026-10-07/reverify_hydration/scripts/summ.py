import json, sys
for line in sys.stdin:
    if not line.startswith(('alpha', 'stable')):
        print(line, end='')
        continue
    lab, js = line.split(' ', 1)
    r = json.loads(js)
    print(lab, 'cd=%s run=%s interactive=%s ws_open=%s click=%s connect=%s IN_WINDOW=%s boot=%s trace=%s' % (
        r['click_delay_ms'], r['run'], r['t_interactive'], r['t_ws_open'], r['t_click'], r['t_connect_sent'],
        r['connect_after_click'], r['boot_router_pathname'], r['trace']) + ' final=' + str(r.get('final_path')), flush=True)
