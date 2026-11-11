"""Capture socket.io frames from a real Chromium session (learn the wire format)."""
import sys, time
from playwright.sync_api import sync_playwright
assert "/envs/driver/" in sys.executable, sys.executable
base = sys.argv[1]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = b.new_page()
    frames = []
    def on_ws(ws):
        print("WS", ws.url)
        ws.on("framesent", lambda f: frames.append(("S", str(f)[:600])))
        ws.on("framereceived", lambda f: frames.append(("R", str(f)[:600])))
    page.on("websocket", on_ws)
    page.on("console", lambda m: print("CONSOLE", m.type, m.text[:300]) if m.type in ("error", "warning") else None)
    page.goto(base, wait_until="networkidle")
    page.wait_for_selector("#count")
    time.sleep(1)
    page.click("#incr"); time.sleep(1)
    print("count", page.inner_text("#count"), "pid", page.inner_text("#pid"))
    print("token", page.evaluate("() => sessionStorage.getItem('token')"))
    for f in frames: print(*f)
    b.close()
