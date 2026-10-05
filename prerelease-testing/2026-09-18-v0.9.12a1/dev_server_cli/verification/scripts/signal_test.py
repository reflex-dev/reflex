"""Signal-handling test for `reflex run`.

usage: signal_test.py <venv> <appdir> <label> <SIG> <proc|group> <logdir> <fp> <bp> [extra reflex args...]
Launches reflex in its own process group (os.setsid in the child), waits for readiness,
sends the signal to the process or the whole group, and reports exit code / timing /
survivors / leftover port bindings / any "exit code 143" line.
"""

import json
import os
import signal
import subprocess
import sys
import time
import urllib.request

venv, appdir, label, sig, target, logdir, fp, bp = sys.argv[1:9]
extra = sys.argv[9:]
SIG = getattr(signal, "SIG" + sig)
logpath = os.path.join(logdir, f"sig_{label}.log")
res = {"label": label, "sig": sig, "target": target, "extra": extra, "fp": fp, "bp": bp}

env = dict(os.environ, REFLEX_TELEMETRY_ENABLED="false")
cmd = [os.path.join(venv, "bin", "reflex"), "run", "--backend-port", bp, *extra]
if "--backend-only" not in extra:
    cmd += ["--frontend-port", fp]
lf = open(logpath, "w")
p = subprocess.Popen(cmd, cwd=appdir, stdout=lf, stderr=subprocess.STDOUT, env=env, preexec_fn=os.setsid)
pgid = os.getpgid(p.pid)
res["pid"], res["pgid"] = p.pid, pgid


def http(url, tmo=3):
    try:
        return urllib.request.urlopen(url, timeout=tmo).status
    except Exception:
        return None


ready_at = None
t0 = time.time()
for _ in range(480):
    if p.poll() is not None:
        res["died_early_rc"] = p.returncode
        break
    ok = http(f"http://127.0.0.1:{bp}/ping") == 200
    if ok and "--backend-only" not in extra:
        ok = http(f"http://127.0.0.1:{fp}/") == 200
    if ok:
        ready_at = round(time.time() - t0, 2)
        break
    time.sleep(0.5)
res["ready_after_s"] = ready_at
if ready_at is None:
    res["READY"] = False
else:
    res["READY"] = True
time.sleep(4)


def members():
    out = subprocess.run(["ps", "-eo", "pid,pgid,comm", "--no-headers"], capture_output=True, text=True).stdout
    return [l.split() for l in out.splitlines() if len(l.split()) >= 2 and l.split()[1] == str(pgid)]


res["members_before"] = [f"{m[0]}:{m[2]}" for m in members()]
t = time.time()
try:
    os.killpg(pgid, SIG) if target == "group" else os.kill(p.pid, SIG)
except ProcessLookupError:
    res["kill_error"] = "ProcessLookupError"
rc = "TIMEOUT_30s"
for _ in range(600):
    if p.poll() is not None:
        rc = p.returncode
        break
    time.sleep(0.05)
res["exit_code"] = rc
res["exit_after_s"] = round(time.time() - t, 2)
time.sleep(2.5)
res["survivors"] = [f"{m[0]}:{m[2]}" for m in members()]
lf.close()
log = open(logpath, errors="replace").read()
res["log_has_143"] = [l for l in log.splitlines() if "143" in l or "exit code" in l.lower()][:5]
res["log_has_error"] = [l for l in log.splitlines() if "[ERROR]" in l or "Traceback" in l][:5]
res["log_tail"] = log.splitlines()[-4:]
ports = subprocess.run([sys.executable, os.environ["PORTS_PY"], fp, bp], capture_output=True, text=True).stdout
res["ports_after"] = ports.strip().splitlines()
# hard cleanup
try:
    os.killpg(pgid, signal.SIGKILL)
except Exception:
    pass
time.sleep(2)
ports2 = subprocess.run([sys.executable, os.environ["PORTS_PY"], fp, bp], capture_output=True, text=True).stdout
res["ports_after_force"] = ports2.strip().splitlines()
print(json.dumps(res, indent=1))
with open(os.path.join(logdir, f"sigres_{label}.json"), "w") as f:
    json.dump(res, f, indent=1)
