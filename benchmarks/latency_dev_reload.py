"""Measure the dev-mode edit->browser cycle using the real `reflex run` CLI."""

from __future__ import annotations

import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent))
from latency_browser import launch_chromium

HERE = Path(__file__).parent
SRC_APP = HERE / "app_dev"  # created by bench.py dev run (rxconfig + benchapp/)
APP_DIR = HERE / "app_reload"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 5
EXTRA_ENV = dict(kv.split("=", 1) for kv in sys.argv[2:])

FRONTEND_PORT = 3123
BACKEND_PORT = 8123


def main():
    if APP_DIR.exists():
        shutil.rmtree(APP_DIR)
    shutil.copytree(
        SRC_APP, APP_DIR, ignore=shutil.ignore_patterns(".states", "__pycache__")
    )
    app_file = APP_DIR / "benchapp" / "benchapp.py"
    src = app_file.read_text()
    assert 'rx.heading("Index")' in src

    log_lines: list[tuple[float, str]] = []
    env = {
        **os.environ,
        "REFLEX_TELEMETRY_ENABLED": "false",
        "NO_COLOR": "1",
        **EXTRA_ENV,
    }
    proc = subprocess.Popen(
        [
            "/home/user/reflex/.venv/bin/reflex",
            "run",
            "--frontend-port",
            str(FRONTEND_PORT),
            "--backend-port",
            str(BACKEND_PORT),
            "--loglevel",
            "info",
        ],
        cwd=APP_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    def pump():
        for line in proc.stdout:  # type: ignore[union-attr]
            log_lines.append((time.perf_counter(), line.rstrip()))

    threading.Thread(target=pump, daemon=True).start()

    results = []
    startup_t0 = time.perf_counter()
    try:
        with sync_playwright() as pw:
            browser = launch_chromium(pw)
            page = browser.new_page()
            ws_events: list[tuple[float, str]] = []

            def on_ws(ws):
                tag = "event" if "_event" in ws.url else "vite"
                ws_events.append((time.perf_counter(), f"{tag}:open"))
                ws.on(
                    "close",
                    lambda: ws_events.append((time.perf_counter(), f"{tag}:close")),
                )
                ws.on(
                    "framereceived",
                    lambda p: ws_events.append((
                        time.perf_counter(),
                        f"{tag}:recv:"
                        + (p if isinstance(p, str) else p.decode())[:100],
                    )),
                )

            page.on("websocket", on_ws)
            deadline = time.time() + 300
            while time.time() < deadline:
                try:
                    page.goto(f"http://localhost:{FRONTEND_PORT}/", timeout=10000)
                    page.wait_for_selector("#hydrated", state="attached", timeout=10000)
                    break
                except Exception:
                    time.sleep(1)
            else:
                (HERE / "devreload_failed.log").write_text(
                    "\n".join(line for _, line in log_lines)
                )
                msg = "app did not start"
                raise RuntimeError(msg)
            startup_s = time.perf_counter() - startup_t0
            page.wait_for_timeout(2000)

            for i in range(1, N + 1):
                old = "Index" if i == 1 else f"Index v{i - 1}"
                new = f"Index v{i}"
                cur = app_file.read_text()
                assert f'rx.heading("{old}")' in cur, cur[-400:]
                n_ws = len(ws_events)
                n_log = len(log_lines)
                t_save = time.perf_counter()
                app_file.write_text(
                    cur.replace(f'rx.heading("{old}")', f'rx.heading("{new}")')
                )
                # Wait until browser shows the new heading and is hydrated again.
                page.wait_for_function(
                    f"document.body.innerText.includes('{new}')", timeout=120000
                )
                t_ui = time.perf_counter()
                page.wait_for_function(
                    "document.querySelector('#hydrated') !== null", timeout=60000
                )
                # ensure a hydrated marker appeared after a reconnect
                page.wait_for_timeout(1500)
                time.perf_counter()
                evs = ws_events[n_ws:]
                logs = log_lines[n_log:]

                def first_ev(prefix, evs=evs, t_save=t_save):
                    for t, e in evs:
                        if e.startswith(prefix):
                            return round((t - t_save) * 1000)
                    return None

                def last_ev(prefix, evs=evs, t_save=t_save):
                    r = None
                    for t, e in evs:
                        if e.startswith(prefix):
                            r = round((t - t_save) * 1000)
                    return r

                def first_log(pattern, logs=logs, t_save=t_save):
                    for t, line in logs:
                        if re.search(pattern, line):
                            return round((t - t_save) * 1000)
                    return None

                results.append({
                    "iter": i,
                    "timeline": [
                        f"+{round((t - t_save) * 1000)}ms {e}" for t, e in evs
                    ],
                    "logs": [
                        f"+{round((t - t_save) * 1000)}ms {line[:120]}"
                        for t, line in logs
                    ],
                    "ui_shows_new_text_ms": round((t_ui - t_save) * 1000),
                    "ws_closed_ms": first_ev("event:close"),
                    "ws_reopened_ms": last_ev("event:open"),
                    "first_delta_after_reopen_ms": last_ev("event:recv:42"),
                    "vite_hmr_update_ms": first_ev('vite:recv:{"type":"update"'),
                    "log_compile_start_ms": first_log(
                        r"Compiling|reload|Reloading|Detected"
                    ),
                    "log_app_running_ms": first_log(
                        r"App running|Started server|Uvicorn running|Listening"
                    ),
                    "n_ws_events": len(evs),
                })
                print(json.dumps(results[-1]), flush=True)
            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
    summary = {
        "startup_s": round(startup_s, 1),
        "extra_env": EXTRA_ENV,
        "iterations": results,
        "median_ui_ms": statistics.median(r["ui_shows_new_text_ms"] for r in results),
        "median_ws_reopen_ms": statistics.median(
            r["ws_reopened_ms"] for r in results if r["ws_reopened_ms"]
        )
        if any(r["ws_reopened_ms"] for r in results)
        else None,
    }
    tag = "_".join(f"{k}{v}" for k, v in EXTRA_ENV.items()) or "default"
    (HERE / f"report_devreload_{tag}.json").write_text(json.dumps(summary, indent=2))
    (HERE / f"devreload_{tag}.log").write_text(
        "\n".join(f"{t:.3f} {line}" for t, line in log_lines)
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
