"""#7653 probe: prod state-schema mismatch with an open tab.

usage: mismatch.py <venv> <port> <mode none|prevent|observe> <out_json>
Starts netapp prod (NA_EXTRA unset) via bin/srv.sh, opens a tab (listener per mode installed by an init
script), restarts the server with NA_EXTRA=1 (changed state schema) while the tab stays open, then records
reflex:state-mismatch events, navigations/reloads, the new-version banner, console warnings, and whether
the tab works afterwards (inc).
"""

import json
import os
import subprocess
import sys
import time

assert "/envs/driver/" in sys.executable, sys.executable
from playwright.sync_api import sync_playwright  # noqa: E402

venv, port, mode, out = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
W = os.environ["W"]
SRV = f"{W}/bin/srv.sh"
base = f"http://localhost:{port}"
label = f"mm_{mode}_{venv}"
srv_env = {k: v for k, v in os.environ.items() if k.lower() != "no_proxy"}


def start(extra: bool):
    env = dict(srv_env)
    env.pop("NA_EXTRA", None)
    if extra:
        env["NA_EXTRA"] = "1"
    subprocess.run([SRV, "start", label, venv, "netapp", "--env", "prod", "--frontend-port", port, "--backend-port", port], env=env, check=True)
    subprocess.run([SRV, "wait", f"{base}/ping", "400"], env={**env, "LABEL": label}, check=True)


def stop():
    subprocess.run([SRV, "stop", label], check=False)


INIT = {
    "none": "",
    "prevent": "window.__mm=[];window.addEventListener('reflex:state-mismatch',e=>{window.__mm.push(e.detail);e.preventDefault();});",
    "observe": "window.__mm=[];window.addEventListener('reflex:state-mismatch',e=>{window.__mm.push(e.detail);try{sessionStorage.setItem('__mm',JSON.stringify(window.__mm))}catch(x){}});",
}[mode]

rec = {"mode": mode, "venv": venv, "console": [], "navs": [], "steps": {}}
start(False)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    if INIT:
        ctx.add_init_script(INIT)
    pg = ctx.new_page()
    pg.on("console", lambda m: rec["console"].append(f"{round(time.time(),1)} {m.type}: {m.text}"[:400]))
    pg.on("framenavigated", lambda f: f == pg.main_frame and rec["navs"].append(f"{round(time.time(),1)} {f.url}"))
    pg.goto(base + "/", wait_until="domcontentloaded")
    pg.wait_for_function("document.querySelector('#count') && document.querySelector('#page')")
    pg.click("#inc")
    pg.wait_for_function("document.querySelector('#count').innerText.includes('count=1')", timeout=15000)
    rec["steps"]["before"] = pg.inner_text("#count")
    stop()
    t_restart = time.time()
    start(True)
    rec["restart_s"] = round(time.time() - t_restart, 1)
    pg.wait_for_timeout(int(os.environ.get("MM_WAIT", "15000")))
    rec["steps"]["banner"] = pg.evaluate("() => !!document.getElementById('reflex-new-version-banner')")
    rec["steps"]["mm_events"] = pg.evaluate("() => window.__mm || null")
    rec["steps"]["count_text"] = pg.evaluate("() => document.querySelector('#count')?.innerText")
    try:
        before = pg.inner_text("#count")
        pg.click("#inc", timeout=3000)
        n = int(before.split("=")[-1]) + 1
        pg.wait_for_function(f"document.querySelector('#count').innerText.includes('count={n}')", timeout=8000)
        rec["steps"]["inc_after"] = f"ok {pg.inner_text('#count')}"
    except Exception as e:  # noqa: BLE001
        rec["steps"]["inc_after"] = f"FAIL {repr(e)[:150]}"
    b.close()
stop()
json.dump(rec, open(out, "w"), indent=1)
print(json.dumps({k: rec[k] for k in ("mode", "venv", "steps", "navs", "restart_s")}, indent=None)[:1500])
for c in rec["console"]:
    if "Hey developer" not in c:
        print("  console:", c[:300])
