"""Break the app module mid-run (import-time error) and see what the backend port does.

usage: break_reload_probe.py <venv> <appdir> <fp> <bp> <label> <logdir>
No signals involved: this is the ordinary "developer saves a file with an error" case.
"""
import json, os, signal, socket, subprocess, sys, time, urllib.request

venv, appdir, fp, bp, label, logdir = sys.argv[1:7]
bp_i = int(bp)
appfile = os.path.join(appdir, "dsc", "dsc.py")
orig = open(appfile).read()
log = open(os.path.join(logdir, f"breakreload_{label}.log"), "w")
env = dict(os.environ, REFLEX_TELEMETRY_ENABLED="false")
p = subprocess.Popen([os.path.join(venv, "bin", "reflex"), "run", "--frontend-port", fp, "--backend-port", bp],
                     cwd=appdir, stdout=log, stderr=subprocess.STDOUT, env=env, preexec_fn=os.setsid)
pgid = os.getpgid(p.pid)
res = {"label": label, "pid": p.pid}

def probe(tag, tmo=6):
    t = time.time()
    try:
        s = socket.create_connection(("127.0.0.1", bp_i), timeout=tmo)
        s.sendall(b"GET /ping HTTP/1.1\r\nHost: l\r\nConnection: close\r\n\r\n")
        d = s.recv(100); s.close()
        out = d.split(b" ")[1].decode() if d.startswith(b"HTTP") else ("EMPTY_RESPONSE" if not d else "ODD")
    except ConnectionRefusedError: out = "CONNECTION_REFUSED"
    except socket.timeout: out = f"TIMEOUT_NO_REPLY_{tmo}s"
    except Exception as e: out = type(e).__name__
    res[tag] = [out, round(time.time() - t, 2)]

try:
    for _ in range(480):
        try:
            if urllib.request.urlopen(f"http://127.0.0.1:{bp}/ping", timeout=3).status == 200: break
        except Exception: pass
        time.sleep(0.5)
    else:
        res["never_ready"] = True
    probe("before_break")
    open(appfile, "w").write(orig + '\n\nraise RuntimeError("BOOM injected by verifier")\n')
    res["edited_at"] = round(time.time(), 2)
    time.sleep(10)
    res["supervisor_alive_10s"] = p.poll() is None
    probe("after_break_10s")
    time.sleep(8)
    probe("after_break_24s")
    # now fix it and see whether it recovers
    open(appfile, "w").write(orig)
    time.sleep(12)
    probe("after_fix_12s")
    time.sleep(8)
    probe("after_fix_20s")
    res["supervisor_alive_end"] = p.poll() is None
finally:
    open(appfile, "w").write(orig)
    try: os.killpg(pgid, signal.SIGKILL)
    except Exception: pass
    time.sleep(2)
    log.close()

print(json.dumps(res, indent=1))
json.dump(res, open(os.path.join(logdir, f"breakreload_{label}.json"), "w"), indent=1)
