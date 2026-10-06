"""Debug: login, /list, click fill, dump websocket frames."""
import json, re, sys, time
from playwright.sync_api import expect, sync_playwright
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import CHROMIUM, W, login, save

BASE = sys.argv[1].rstrip("/")
LABEL = sys.argv[2]
frames = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROMIUM)
    ctx = b.new_context()
    page = ctx.new_page()
    def on_ws(ws):
        ws.on("framesent", lambda d: frames.append(["sent", round(time.time(), 2), str(d)[:1500]]))
        ws.on("framereceived", lambda d: frames.append(["recv", round(time.time(), 2), str(d)[:1500]]))
    page.on("websocket", on_ws)
    page.goto(BASE + "/list")
    page.wait_for_url(re.compile("/login"), timeout=45000)
    login(page, "alice")
    page.wait_for_url(BASE + "/list", timeout=45000)
    expect(page.locator("#list-user")).to_have_text("alice", timeout=45000)
    frames.append(["MARK", time.time(), "click fill"])
    page.locator("#fill").click()
    page.wait_for_timeout(5000)
    print("progress", page.locator("#progress").inner_text(), "items", page.locator(".item").all_inner_texts(), "bgpid", page.locator("#bg-pid").inner_text())
    page.reload()
    page.wait_for_timeout(3000)
    print("after reload progress", page.locator("#progress").inner_text(), "items", page.locator(".item").all_inner_texts(), "bgpid", page.locator("#bg-pid").inner_text())
    b.close()
save(f"debug-fill-{LABEL}.json", frames)
i = [k for k, f in enumerate(frames) if f[0] == "MARK"][0]
for f in frames[i:i+12]:
    print(f[0], f[2][:700])
