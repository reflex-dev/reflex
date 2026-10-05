"""Drive deltaapp and record delta shapes. Usage: drive_delta.py <url> <outdir> <label>"""
import json, re, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE, OUT, LABEL = sys.argv[1].rstrip("/"), Path(sys.argv[2]), sys.argv[3]
OUT.mkdir(parents=True, exist_ok=True)
res = {"label": LABEL, "steps": [], "console": [], "page_errors": [], "failed": [], "bad": []}
frames = []

def keys_of(f):
    m = re.search(r'\["event",(\{.*\})\]$', f)
    if not m:
        return None
    try:
        d = json.loads(m.group(1)).get("delta", {})
    except Exception:
        return None
    return {k.split(".")[-1]: sorted(v) for k, v in d.items()}

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    pg = ctx.new_page()
    pg.on("console", lambda m: res["console"].append({"type": m.type, "text": m.text[:400]}))
    pg.on("pageerror", lambda e: res["page_errors"].append(str(e)[:600]))
    pg.on("requestfailed", lambda r: res["failed"].append({"url": r.url, "err": str(r.failure)}))
    pg.on("response", lambda r: res["bad"].append({"url": r.url, "status": r.status}) if r.status >= 400 else None)
    pg.on("websocket", lambda ws: ws.on("framereceived", lambda f: frames.append(("recv", time.time(), f if isinstance(f, str) else "<bin>"))))

    def vals():
        out = {}
        for i in ("v_unc", "v_cac", "v_sunc", "v_scount", "v_ocount", "v_loglen", "v_vis", "v_cs"):
            try:
                out[i] = pg.inner_text("#" + i)
            except Exception:
                out[i] = "<missing>"
        return out

    def step(name, fn, settle=1.2):
        n0 = len(frames)
        fn()
        time.sleep(settle)
        fr = [keys_of(f[2]) for f in frames[n0:] if f[0] == "recv"]
        res["steps"].append({"step": name, "values": vals(), "delta_keys": [x for x in fr if x is not None]})

    pg.goto(BASE + "/", wait_until="load")
    pg.wait_for_selector("#v_cac", timeout=90000)
    time.sleep(2.0)
    res["steps"].append({"step": "after_load", "values": vals(),
                         "delta_keys": [x for x in (keys_of(f[2]) for f in frames if f[0] == "recv") if x is not None]})

    step("bump_x3", lambda: [pg.click("#b_bump"), time.sleep(0.3), pg.click("#b_bump"), time.sleep(0.3), pg.click("#b_bump")])
    step("show", lambda: pg.click("#b_show"))
    step("bump_visible", lambda: pg.click("#b_bump"))
    step("hide", lambda: pg.click("#b_hide"))
    step("bump_hidden", lambda: pg.click("#b_bump"))
    step("show_again", lambda: pg.click("#b_show"))
    step("sbump_x2", lambda: [pg.click("#b_sbump"), time.sleep(0.3), pg.click("#b_sbump")])
    step("chain", lambda: pg.click("#b_chain"))
    step("storm", lambda: pg.click("#b_storm"), settle=3.0)
    step("client_state", lambda: pg.fill("#cs_in", "CSVAL"))
    pg.reload(wait_until="load")
    pg.wait_for_selector("#v_cac", timeout=90000)
    time.sleep(2.0)
    res["steps"].append({"step": "after_reload", "values": vals(), "delta_keys": []})
    pg.screenshot(path=str(OUT / f"{LABEL}_delta.png"))
    res["recv_frames"] = len(frames)
    ctx.close(); b.close()

(OUT / f"{LABEL}_delta_result.json").write_text(json.dumps(res, indent=1))
for s in res["steps"]:
    print(s["step"], json.dumps(s["values"]))
    for dk in s["delta_keys"]:
        print("    ", json.dumps(dk))
print("CONSOLE ERRORS:", [c for c in res["console"] if c["type"] == "error"])
print("PAGE ERRORS:", res["page_errors"])
print("FAILED:", res["failed"], "BAD:", res["bad"])
