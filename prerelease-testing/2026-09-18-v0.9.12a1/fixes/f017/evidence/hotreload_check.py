"""Ping the dev backend at 20 Hz across a harmless hot reload.

usage: hotreload_check.py <venv> <appdir> <fp> <bp> <label> <logdir>
"""
import json, os, signal, subprocess, sys, time, urllib.request

venv, appdir, fp, bp, label, logdir = sys.argv[1:7]
appfile = os.path.join(appdir, "dsc", "dsc.py")
orig = open(appfile).read()
log = open(os.path.join(logdir, f"hotreload_{label}.log"), "w")
env = dict(os.environ, REFLEX_TELEMETRY_ENABLED="false")
p = subprocess.Popen([os.path.join(venv, "bin", "reflex"), "run", "--frontend-port", fp, "--backend-port", bp],
                     cwd=appdir, stdout=log, stderr=subprocess.STDOUT, env=env, preexec_fn=os.setsid)
pgid = os.getpgid(p.pid)
res = {"label": label, "pid": p.pid}
try:
    for _ in range(480):
        try:
            if urllib.request.urlopen(f"http://127.0.0.1:{bp}/ping", timeout=3).status == 200:
                break
        except Exception:
            pass
        time.sleep(0.5)
    else:
        res["never_ready"] = True
    tsv = os.path.join(logdir, f"hotreload_{label}.tsv")
    ping = subprocess.Popen([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "ping_probe.py"),
                             bp, "30", tsv], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
    time.sleep(5)
    open(appfile, "w").write(orig.replace('HEADING = "dsc v5-reload"', 'HEADING = "dsc v5-reload-edit"'))
    res["edited_at"] = round(time.time(), 2)
    time.sleep(10)
    open(appfile, "w").write(orig)
    res["restored_at"] = round(time.time(), 2)
    res["ping_summary"] = ping.communicate(timeout=120)[0]
finally:
    open(appfile, "w").write(orig)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except Exception:
        pass
    time.sleep(2)
    log.close()

print(json.dumps(res, indent=1))
json.dump(res, open(os.path.join(logdir, f"hotreload_{label}.json"), "w"), indent=1)
