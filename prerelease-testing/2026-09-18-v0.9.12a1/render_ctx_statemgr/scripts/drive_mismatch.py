"""FINDING-036 re-test: a delta for a substate the compiled frontend has no dispatcher for.

Usage: python drive_mismatch.py <frontend_url> <outdir> <label>
"""
import json, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE, OUT, LABEL = sys.argv[1].rstrip("/"), Path(sys.argv[2]), sys.argv[3]
OUT.mkdir(parents=True, exist_ok=True)
R = {"label": LABEL, "base": BASE}
console, errs, frames = [], [], []

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context(); pg = ctx.new_page()
    pg.on("console", lambda m: console.append({"type": m.type, "text": m.text[:700]}))
    pg.on("pageerror", lambda e: errs.append(str(e)[:600]))
    pg.on("websocket", lambda ws: (
        ws.on("framereceived", lambda f: frames.append(("recv", time.time(), f if isinstance(f, str) else "<bin>"))),
        ws.on("framesent", lambda f: frames.append(("sent", time.time(), f if isinstance(f, str) else "<bin>")))))
    pg.goto(BASE + "/", wait_until="load")
    pg.wait_for_selector("#a-btn", timeout=90000)
    time.sleep(5.0)
    R["A_after_load"] = pg.inner_text('[data-value="A"]')
    R["dual_after_load"] = pg.inner_text("#dual-value")
    sent_before = sum(1 for k, _, _ in frames if k == "sent")
    pg.click("#a-btn"); pg.click("#a-btn"); pg.click("#c-btn")
    time.sleep(3.0)
    R["A_after_clicks"] = pg.inner_text('[data-value="A"]')
    R["C_after_clicks"] = pg.inner_text('[data-value="C"]')
    R["sent_frames_from_clicks"] = sum(1 for k, _, _ in frames if k == "sent") - sent_before
    R["events_reach_backend"] = R["sent_frames_from_clicks"] > 0
    R["ui_updates"] = R["A_after_clicks"] != R["A_after_load"]
    pg.screenshot(path=str(OUT / f"{LABEL}.png"))
    # does a reload recover?
    pg.reload(wait_until="load"); pg.wait_for_selector("#a-btn", timeout=90000); time.sleep(4.0)
    sb = sum(1 for k, _, _ in frames if k == "sent")
    pg.click("#a-btn"); time.sleep(2.5)
    R["after_reload_A"] = pg.inner_text('[data-value="A"]')
    R["after_reload_sent_frames"] = sum(1 for k, _, _ in frames if k == "sent") - sb
    R["console_errors"] = [c for c in console if c["type"] == "error"]
    R["page_errors"] = errs
    R["recv_frames"] = sum(1 for k, _, _ in frames if k == "recv")
    b.close()

(OUT / f"{LABEL}_result.json").write_text(json.dumps(R, indent=2))
(OUT / f"{LABEL}_frames.txt").write_text("\n".join(f"{k} {t:.3f} {f[:1200]}" for k, t, f in frames))
print(json.dumps(R, indent=2)[:4000])
