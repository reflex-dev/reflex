"""Connection backoff: load the frontend while the backend is unreachable (or a
proxy closes the connection), count socket attempts over WINDOW seconds, check the
connection error toast, then optionally start the backend and check recovery.

Usage: t_backoff.py <frontend_url> <report.json> <shots_prefix> <window_s> [--start-backend "<shell cmd>" --backend-cwd DIR]
"""
import os
import shlex
import subprocess
import sys
import time

from pwlib import Capture, browser, sync_playwright

url, report, shots, window = sys.argv[1:5]
window = float(window)
args = sys.argv[5:]
start_cmd = args[args.index("--start-backend") + 1] if "--start-backend" in args else None
backend_cwd = args[args.index("--backend-cwd") + 1] if "--backend-cwd" in args else None
results = {}
proc = None
with sync_playwright() as p:
    b = browser(p)
    page = b.new_page()
    cap = Capture(page)
    page.goto(url)
    # wait_for_timeout keeps the sync Playwright event loop pumping so event timestamps are real
    page.wait_for_timeout(window * 1000)
    page.screenshot(path=f"{shots}_1_backend_down.png")
    attempts = [r for r in cap.requests if "_event" in r["url"] or "socket.io" in r["url"]]
    ws_opens = [f for f in cap.ws if f["event"] == "open"]
    results["http_attempts_in_window"] = len(attempts)
    results["ws_opens_in_window"] = len(ws_opens)
    gaps = [round(b_["t"] - a_["t"], 3) for a_, b_ in zip(ws_opens, ws_opens[1:])]
    results["ws_open_gaps"] = gaps
    results["toast_text"] = page.evaluate(
        "() => Array.from(document.querySelectorAll('[data-sonner-toast], [role=status], [role=alert]')).map(e => e.innerText).join(' | ')"
    )
    results["body_text_snippet"] = page.locator("body").inner_text()[:500]
    if start_cmd:
        env = {k: v for k, v in os.environ.items() if k.lower() not in ("no_proxy",)}
        proc = subprocess.Popen(start_cmd, shell=True, cwd=backend_cwd, env=env, stdout=open(f"{shots}_backend.log", "w"), stderr=subprocess.STDOUT)
        results["backend_pid"] = proc.pid
        t_start = time.time()
        connected = False
        for _ in range(90):
            page.wait_for_timeout(1000)
            if page.evaluate("() => !!document.querySelector('#inc')"):
                try:
                    page.click("#inc", timeout=1000)
                    page.wait_for_selector("#count:has-text('count: 1')", timeout=1500)
                    connected = True
                    break
                except Exception:
                    pass
        results["recovered"] = connected
        results["recovery_seconds"] = round(time.time() - t_start, 1)
        page.wait_for_timeout(3000)
        results["toast_after_recovery"] = page.evaluate(
            "() => Array.from(document.querySelectorAll('[data-sonner-toast], [role=status], [role=alert]')).map(e => e.innerText).join(' | ')"
        )
        page.screenshot(path=f"{shots}_2_recovered.png")
    results["anomalies"] = cap.anomalies()[:40]
    results["n_anomalies"] = len(cap.anomalies())
    cap.dump(report, results=results)
    b.close()
if proc:
    proc.terminate()
    try:
        proc.wait(10)
    except Exception:
        proc.kill()
for k, v in results.items():
    print(k, "=", v)
