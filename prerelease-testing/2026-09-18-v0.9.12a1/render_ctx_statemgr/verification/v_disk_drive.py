"""Grab the client token, click bump N times, return token. Usage: v_disk_drive.py <url> <outdir> <label> <nbumps>"""
import json, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright
BASE, OUT, LABEL, N = sys.argv[1].rstrip("/"), Path(sys.argv[2]), sys.argv[3], int(sys.argv[4])
OUT.mkdir(parents=True, exist_ok=True)
R = {"label": LABEL}
console = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_context().new_page()
    pg.on("console", lambda m: console.append({"type": m.type, "text": m.text[:400]}))
    pg.goto(BASE + "/", wait_until="load")
    pg.wait_for_selector("#bump", timeout=90000)
    time.sleep(2.0)
    R["token"] = pg.inner_text("#token")
    for _ in range(N):
        pg.click("#bump"); time.sleep(0.15)
    time.sleep(1.5)
    R["counter"] = pg.inner_text("#counter")
    R["value"] = pg.inner_text("#value")
    pg.screenshot(path=str(OUT / f"{LABEL}.png"))
    R["console_errors"] = [c for c in console if c["type"] == "error"]
    b.close()
(OUT / f"{LABEL}_result.json").write_text(json.dumps(R, indent=2))
print(json.dumps(R, indent=2))
