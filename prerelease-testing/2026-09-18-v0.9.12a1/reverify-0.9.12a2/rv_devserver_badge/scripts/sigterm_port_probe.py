"""After SIGTERM to the `reflex run` pid only, probe what the backend port does.

usage: sigterm_port_probe.py <venv> <appdir> <fp> <bp> <label> <logdir>
"""
import json, os, signal, socket, subprocess, sys, time, urllib.request
venv, appdir, fp, bp, label, logdir = sys.argv[1:7]
bp_i = int(bp)
log = open(os.path.join(logdir, f"portprobe_{label}.log"), "w")
env = dict(os.environ, REFLEX_TELEMETRY_ENABLED="false")
p = subprocess.Popen([os.path.join(venv,"bin","reflex"),"run","--frontend-port",fp,"--backend-port",bp],
                     cwd=appdir, stdout=log, stderr=subprocess.STDOUT, env=env, preexec_fn=os.setsid)
pgid = os.getpgid(p.pid)
res = {"label": label, "pid": p.pid}
for _ in range(480):
    try:
        if urllib.request.urlopen(f"http://127.0.0.1:{bp}/ping", timeout=3).status == 200: break
    except Exception: pass
    time.sleep(0.5)
else:
    res["never_ready"] = True
def probe(tag, tmo=6):
    t=time.time()
    try:
        s=socket.create_connection(("127.0.0.1",bp_i),timeout=tmo)
        s.sendall(b"GET /ping HTTP/1.1\r\nHost: l\r\nConnection: close\r\n\r\n")
        d=s.recv(100); s.close()
        out = d.split(b" ")[1].decode() if d.startswith(b"HTTP") else ("EMPTY_RESPONSE" if not d else "ODD")
    except ConnectionRefusedError: out="CONNECTION_REFUSED"
    except socket.timeout: out=f"TIMEOUT_NO_REPLY_{tmo}s"
    except Exception as e: out=f"{type(e).__name__}"
    res[tag]=[out, round(time.time()-t,2)]
probe("before_sigterm")
os.kill(p.pid, signal.SIGTERM)
time.sleep(8)
res["still_alive"] = p.poll() is None
probe("after_sigterm_8s")
time.sleep(10)
probe("after_sigterm_18s")
try: os.killpg(pgid, signal.SIGKILL)
except Exception: pass
time.sleep(2)
probe("after_sigkill_group")
log.close()
print(json.dumps(res, indent=1))
json.dump(res, open(os.path.join(logdir, f"portprobe_{label}.json"),"w"), indent=1)
