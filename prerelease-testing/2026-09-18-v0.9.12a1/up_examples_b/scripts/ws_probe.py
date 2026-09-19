"""Capture websocket frames while clicking #bump, to see which vars appear in deltas."""
import sys, json
from pathlib import Path
from playwright.sync_api import sync_playwright

url, out = sys.argv[1], Path(sys.argv[2])
frames = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    pg.on("websocket", lambda ws: ws.on("framereceived", lambda pl: frames.append(pl if isinstance(pl, str) else "<bin>")))
    pg.goto(url, wait_until="load", timeout=60000)
    pg.wait_for_timeout(3000)
    mark = len(frames)
    pg.click("#bump"); pg.wait_for_timeout(1500)
    pg.click("#bump"); pg.wait_for_timeout(1500)
    b.close()
after = frames[mark:]
out.write_text("\n".join(after))
txt = "\n".join(after)
print("frames after bump:", len(after))
print("mentions 'steady':", txt.count("steady"))
print("mentions 'tick':", txt.count("tick"))
for f in after:
    if "delta" in f or "tick" in f:
        print(f[:900]); print("---")
