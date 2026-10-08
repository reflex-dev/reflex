"""Start prod+redis server, connect one tab, stop server, list leftover token records in redis.

Usage: token_leak_check.py <venv> <port> [rounds]
"""
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hydcommon import CHROMIUM, wait_hydrated  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

H = Path(__file__).resolve().parent.parent
venv, port = sys.argv[1], int(sys.argv[2])
rounds = int(sys.argv[3]) if len(sys.argv) > 3 else 2
name = f"tokleak-{venv}"


def redis_keys():
    out = subprocess.run(["redis-cli", "-p", "8149", "--scan", "--pattern", "token_manager_socket_record_*"], capture_output=True, text=True)
    return sorted(out.stdout.split())


for i in range(rounds):
    subprocess.run(["redis-cli", "-p", "8149", "flushall"], capture_output=True)
    print(subprocess.run([str(H / "srv.sh"), "start", name, venv, "prod", str(port), str(port), "REFLEX_REDIS_URL=redis://localhost:8149"], capture_output=True, text=True).stdout.strip())
    print(subprocess.run([sys.executable, str(H / "drivers" / "waitsrv.py"), "600", f"http://localhost:{port}/ping", f"http://localhost:{port}/"], capture_output=True, text=True).stdout.strip())
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=CHROMIUM)
        ctx = b.new_context()
        p = ctx.new_page()
        p.goto(f"http://localhost:{port}/")
        print("hydrated", wait_hydrated(p))
        tok = p.evaluate("sessionStorage.getItem('token')")
        print("token", tok, "keys while connected", redis_keys())
        # stop the server with the tab still open
        print(subprocess.run([str(H / "srv.sh"), "stop", name], capture_output=True, text=True).stdout.strip())
        time.sleep(1)
        left = redis_keys()
        print(f"ROUND {i} {venv}: leftover keys after stop: {left} (tab token key present: {any(tok in k for k in left)})")
        b.close()
