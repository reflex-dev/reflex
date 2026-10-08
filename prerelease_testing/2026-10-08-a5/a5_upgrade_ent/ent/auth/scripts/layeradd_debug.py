"""Does clicking a base-layer switch send a layeradd event over the websocket? Usage: layeradd_debug.py <base>"""
import json
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import CHROMIUM, attach  # noqa: E402
from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROMIUM)
    page = b.new_page()
    d = {}
    attach(page, d)
    sent = []
    page.on("websocket", lambda ws: ws.on("framesent", lambda f: sent.append(f[:160]) if isinstance(f, str) and "_event" in f else None))
    page.goto(BASE + "/layers")
    page.wait_for_timeout(6000)
    n0 = len(sent)
    page.locator("#base-topo").click()
    page.wait_for_timeout(3000)
    print("frames sent after switch:", json.dumps(sent[n0:], indent=0)[:1500])
    print("layer adds text:", page.locator("#layer-adds").inner_text())
    print("console:", [c["text"][:200] for c in d["console"] if c["type"] in ("error", "warning") and "TUNNEL" not in c["text"]][:6])
    print("page errors:", d["page_errors"][:3])
    b.close()
