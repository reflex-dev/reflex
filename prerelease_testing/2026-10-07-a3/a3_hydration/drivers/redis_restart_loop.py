"""Repeat: prod+redis server, tab increments counter, stop server (tab open), check leftover token keys and
shutdown panic, restart, check token/counter survive. Usage: redis_restart_loop.py <venv> <port> <rounds>"""
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hydcommon import CHROMIUM, text, wait_hydrated, wait_text, wait_until  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

H = Path(__file__).resolve().parent.parent
venv, port, rounds = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
name = f"rloop-{venv}"
ENV = "REFLEX_REDIS_URL=redis://localhost:8149"


def sh(*a):
    return subprocess.run(list(a), capture_output=True, text=True).stdout.strip()


def start():
    out = sh(str(H / "srv.sh"), "start", name, venv, "prod", str(port), str(port), ENV)
    sh(sys.executable, str(H / "drivers" / "waitsrv.py"), "600", f"http://localhost:{port}/ping", f"http://localhost:{port}/")
    return out.split("log=")[-1]


def keys():
    return sorted(sh("redis-cli", "-p", "8149", "--scan", "--pattern", "token_manager_socket_record_*").split())


results = []
sh("redis-cli", "-p", "8149", "flushall")
log = start()
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROMIUM)
    ctx = b.new_context()
    p = ctx.new_page()
    new_tokens = []
    p.on("websocket", lambda ws: ws.on("framereceived", lambda f: isinstance(f, str) and "new_token" in f and new_tokens.append(f)))
    p.goto(f"http://localhost:{port}/")
    wait_hydrated(p)
    for i in range(rounds):
        tok = p.evaluate("sessionStorage.getItem('token')")
        c0 = int(text(p, "#counter") or 0)
        p.click("#inc")
        wait_text(p, "#counter", str(c0 + 1))
        before = text(p, "#counter")
        sh(str(H / "srv.sh"), "stop", name)
        time.sleep(1)
        left = keys()
        panic = "panicked" in Path(log).read_text()
        n_new_before = len(new_tokens)
        log = start()
        wait_until(p, lambda: text(p, "#hyd-flag") == "H:yes" and len([1]) and p.evaluate("1"), 30000)
        p.wait_for_timeout(4000)
        after_tok = p.evaluate("sessionStorage.getItem('token')")
        res = {"round": i, "counter_before": before, "counter_after": text(p, "#counter"), "token_same": after_tok == tok,
               "leftover_keys_after_stop": [k[-36:] for k in left], "stale_key_is_tab_token": any(tok in k for k in left),
               "shutdown_panic_in_prev_log": panic, "new_token_frames": new_tokens[n_new_before:]}
        print(json.dumps(res), flush=True)
        results.append(res)
    b.close()
sh(str(H / "srv.sh"), "stop", name)
Path(H / "results" / f"redis_restart_loop_{venv}.json").write_text(json.dumps(results, indent=1))
