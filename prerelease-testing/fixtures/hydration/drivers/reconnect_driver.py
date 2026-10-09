"""Reconnect / restart / offline scenarios with server control (prod, single port).

Usage:
  NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python reconnect_driver.py \
     --venv alpha --port 3221 --manager memory|disk|redis --out results/reconnect-alpha-memory [--default-change]
The server is started/stopped through scripts/srv_hydapp.sh (name recon-<venv>-<manager>); REDIS_PORT (default 8149).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hydcommon import (  # noqa: E402
    CHROMIUM,
    TIMELINE_JS,
    Recorder,
    jtext,
    save_json,
    series,
    storage_dump,
    summarize_frames,
    text,
    timeline,
    wait_hydrated,
    wait_text,
    wait_until,
)
from playwright.sync_api import sync_playwright  # noqa: E402

H = Path(__file__).resolve().parent.parent
REDIS_PORT = os.environ.get("REDIS_PORT", "8149")
SRV = H / "scripts" / "srv_hydapp.sh"
WAIT = H / "drivers" / "waitsrv.py"
PY = sys.executable


def srv_start(name, venv, port, extra_env):
    out = subprocess.run([str(SRV), "start", name, venv, "prod", str(port), str(port), *extra_env], capture_output=True, text=True)
    print(out.stdout.strip(), out.stderr.strip(), flush=True)
    t0 = time.time()
    w = subprocess.run([PY, str(WAIT), "600", f"http://localhost:{port}/ping", f"http://localhost:{port}/"], capture_output=True, text=True)
    print(w.stdout.strip(), flush=True)
    return round(time.time() - t0, 1)


def srv_stop(name):
    out = subprocess.run([str(SRV), "stop", name], capture_output=True, text=True)
    print(out.stdout.strip(), flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--venv", required=True)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--manager", required=True, choices=["memory", "disk", "redis"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--default-change", action="store_true")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    base = f"http://localhost:{args.port}"
    name = f"recon-{args.venv}-{args.manager}"
    env = []
    if args.manager == "memory":
        env.append("REFLEX_STATE_MANAGER_MODE=memory")
    elif args.manager == "redis":
        env.append(f"REFLEX_REDIS_URL=redis://localhost:{REDIS_PORT}")
    r: dict = {"venv": args.venv, "manager": args.manager}
    rec = Recorder()
    r["startup_s"] = srv_start(name, args.venv, args.port, env)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=CHROMIUM)
        if args.default_change:
            # Phase A: fresh profile, one visit with the original default.
            ca = browser.new_context()
            pa = ca.new_page()
            rec.attach(pa, "dc_a")
            pa.goto(base + "/")
            wait_hydrated(pa)
            pa.wait_for_timeout(1000)
            r["dc_phaseA_sub_ls"] = text(pa, "#sub-ls")
            r["dc_phaseA_storage"] = storage_dump(pa)
            ca.storage_state(path=str(out / "dc_storage_state.json"))
            ca.close()
        ctx = browser.new_context()
        ctx.add_init_script(TIMELINE_JS)
        p = ctx.new_page()
        rec.attach(p, "main")
        p.goto(base + "/")
        wait_hydrated(p)
        for _ in range(3):
            p.click("#inc")
        wait_text(p, "#counter", "3")
        p.click("#set-values")
        p.click("#set-sub")
        wait_text(p, "#ls-plain", "ls-A")
        wait_text(p, "#sub-ls", "sub-ls-S1")
        p.wait_for_timeout(500)
        r["before"] = {k: text(p, "#" + k) for k in ["counter", "ls-plain", "sub-ls", "sub-uuid", "load-count"]}
        token = p.evaluate("sessionStorage.getItem('token')")
        n_frames_before = len(rec.ws_frames)
        # Kill the server while the tab stays open.
        srv_stop(name)
        p.wait_for_timeout(3000)
        r["while_down"] = {"hyd": text(p, "#hyd-flag"), "counter": text(p, "#counter"), "screenshot": str(out / "while_down.png")}
        p.screenshot(path=str(out / "while_down.png"), full_page=True)
        r["while_down"]["body_has_connection_msg"] = p.evaluate("document.body.innerText.slice(0, 400)")
        restart_env = list(env)
        if args.default_change:
            restart_env.append("HYD_SUB_LS_DEFAULT=sub-ls-NEWDEFAULT")
        r["restart_s"] = srv_start(name, args.venv, args.port, restart_env)
        t0 = time.time()
        ok = wait_until(p, lambda: text(p, "#hyd-flag") == "H:yes" and text(p, "#load-count") not in (None, r["before"]["load-count"]) and text(p, "#load-count"), 60000)
        p.wait_for_timeout(2500)
        r["after_restart"] = {k: text(p, "#" + k) for k in ["counter", "ls-plain", "sub-ls", "sub-uuid", "load-count", "hyd-flag"]}
        r["after_restart"]["rehydrated_in_s"] = round(time.time() - t0, 1) if ok else None
        r["after_restart"]["token_same"] = p.evaluate("sessionStorage.getItem('token')") == token
        tr = jtext(p, "#trace") or []
        r["after_restart"]["trace_tail"] = tr[-4:]
        new_frames = rec.ws_frames[n_frames_before:]
        summ = summarize_frames(new_frames, "main")
        r["after_restart"]["boot_events_sent"] = [f for f in summ if f["kind"] == "connect" and f["dir"] == "out"]
        r["after_restart"]["frames"] = summ[:20]
        r["after_restart"]["hyd_series_tail"] = series(timeline(p), "hyd-flag")[-6:]
        p.screenshot(path=str(out / "after_restart.png"), full_page=True)
        # Interact after restart.
        p.click("#inc")
        p.wait_for_timeout(800)
        r["after_restart"]["counter_after_click"] = text(p, "#counter")
        # Offline flap.
        n0 = len(rec.ws_frames)
        lc0 = text(p, "#load-count")
        ctx.set_offline(True)
        p.wait_for_timeout(4000)
        r["offline"] = {"hyd_while_offline": text(p, "#hyd-flag"), "ws_events": [e for e in rec.ws_events if e["t"] > rec.now() - 5]}
        ctx.set_offline(False)
        p.wait_for_timeout(5000)
        r["offline"]["after_online"] = {k: text(p, "#" + k) for k in ["counter", "ls-plain", "load-count", "hyd-flag"]}
        r["offline"]["load_count_before"] = lc0
        r["offline"]["frames"] = summarize_frames(rec.ws_frames[n0:], "main")[:12]
        p.click("#inc")
        p.wait_for_timeout(800)
        r["offline"]["counter_after_click"] = text(p, "#counter")
        ctx.close()
        if args.default_change:
            cb = browser.new_context(storage_state=str(out / "dc_storage_state.json"))
            pb = cb.new_page()
            rec.attach(pb, "dc_b")
            pb.goto(base + "/")
            wait_hydrated(pb)
            pb.wait_for_timeout(800)
            r["dc_phaseB_returning_visitor_sub_ls"] = text(pb, "#sub-ls")
            cb.close()
            cc = browser.new_context()
            pc = cc.new_page()
            rec.attach(pc, "dc_c")
            pc.goto(base + "/")
            wait_hydrated(pc)
            pc.wait_for_timeout(500)
            r["dc_phaseB_fresh_visitor_sub_ls"] = text(pc, "#sub-ls")
            cc.close()
        browser.close()
    srv_stop(name)
    r["anomalies"] = rec.anomalies()
    save_json(out / "result.json", r)
    save_json(out / "raw.json", rec.dump())
    print(json.dumps({k: v for k, v in r.items() if k not in ("anomalies",)}, indent=1, default=str)[:6000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
