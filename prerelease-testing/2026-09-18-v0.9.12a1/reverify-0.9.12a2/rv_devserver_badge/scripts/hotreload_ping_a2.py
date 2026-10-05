"""#7114 intact check: 20 Hz /ping loop across two harmless hot reloads on a2.

usage: hotreload_ping_a2.py <venv> <appdir> <fp> <bp> <label> <logdir>
"""
import json, os, signal, subprocess, sys, threading, time, urllib.request

venv, appdir, fp, bp, label, logdir = sys.argv[1:7]
appfile = os.path.join(appdir, "dsc", "dsc.py")
orig = open(appfile).read()
assert 'HEADING = "dsc v5-reload"' in orig, "heading anchor missing"
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
    probe_out = os.path.join(logdir, f"hotreload_{label}.tsv")
    probe = subprocess.Popen([sys.executable, os.path.join(os.path.dirname(__file__), "ping_probe.py"), bp, "42", probe_out],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    time.sleep(8)
    open(appfile, "w").write(orig.replace('HEADING = "dsc v5-reload"', 'HEADING = "dsc v5-reload-EDIT1"'))
    res["edit1_at"] = 8
    time.sleep(16)
    open(appfile, "w").write(orig.replace('HEADING = "dsc v5-reload"', 'HEADING = "dsc v5-reload-EDIT2"'))
    res["edit2_at"] = 24
    out = probe.communicate(timeout=120)[0]
    res["probe"] = out.strip().splitlines()
    srv = open(os.path.join(logdir, f"hotreload_{label}.log")).read()
    res["reload_lines"] = [l for l in srv.splitlines() if "Changes detected" in l or "Spawning worker" in l or "Stopping worker" in l]
    open(appfile, "w").write(orig)
    time.sleep(10)
    try:
        res["final_ping"] = urllib.request.urlopen(f"http://127.0.0.1:{bp}/ping", timeout=5).status
    except Exception as e:
        res["final_ping"] = f"{type(e).__name__}"
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
