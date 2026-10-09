"""Explorer's drive_storage_only.py flow (tp_patterns /storage) plus websocket frame capture.

Usage: drive_tp_ws.py <base_url> <out_json>
"""
import json
import sys
import time

from tpdrive import browser, wait_text

assert ("/envs/" + __import__("os").environ.get("DRIVER", "driver") + "/") in sys.executable, sys.executable
BASE = sys.argv[1].rstrip("/")
frames, phase = [], {"p": "initial"}
t0 = time.time()


def on_ws(ws):
    frames.append({"t": round(time.time() - t0, 3), "phase": phase["p"], "dir": "open", "data": ws.url})
    ws.on("framesent", lambda d: frames.append({"t": round(time.time() - t0, 3), "phase": phase["p"], "dir": "sent", "data": str(d)[:6000]}))
    ws.on("framereceived", lambda d: frames.append({"t": round(time.time() - t0, 3), "phase": phase["p"], "dir": "recv", "data": str(d)[:6000]}))


with browser() as b:
    ctx = b.new_context()
    page = ctx.new_page()
    page.on("websocket", on_ws)
    page.goto(BASE + "/storage", wait_until="networkidle")
    wait_text(page, "#store_log", "on_load")
    page.evaluate("() => localStorage.setItem('tp_ls_cv', 'bad')")
    phase["p"] = "reload"
    page.goto(BASE + "/storage", wait_until="networkidle")
    wait_text(page, "#store_log", "on_load")
    page.wait_for_timeout(2000)
    res = {
        "tp_ls_cv": page.evaluate("() => localStorage.getItem('tp_ls_cv')"),
        "ui_ls_cv": page.locator("#ls_cv").inner_text(),
        "ui_cv_check": page.locator("#cv_check").inner_text(),
    }
    print("RESULT", json.dumps(res))
json.dump({"result": res, "frames": frames}, open(sys.argv[2], "w"), indent=1)
for f in frames:
    if f["phase"] == "reload" and f["dir"] != "open" and ("ls_cv" in f["data"] or "hydrate" in f["data"] or "store_state" in f["data"]):
        print(f"  {f['t']:7.3f} {f['dir']:4s} {f['data'][:700]}")
