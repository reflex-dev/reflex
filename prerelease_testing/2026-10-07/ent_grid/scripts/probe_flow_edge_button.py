"""Probe the overview button-edge × (rx.run_script(set_edges(filter(get_edges())))). Usage: <base_url> <expected_venv>"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from qa_common import assert_driver_and_server  # noqa: E402
from playwright.sync_api import sync_playwright

base, venv = sys.argv[1:3]
info = assert_driver_and_server(venv)
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    p = b.new_page(viewport={"width": 1400, "height": 900})
    msgs = []
    p.on("console", lambda m: msgs.append(f"{m.type}: {m.text[:400]}"))
    p.on("pageerror", lambda e: msgs.append(f"pageerror: {e}"))
    sent = []
    p.on("websocket", lambda ws: ws.on("framesent", lambda f: sent.append(str(f)[:300])))
    p.goto(base + "/overview", wait_until="networkidle")
    p.wait_for_selector(".react-flow__node")
    p.wait_for_timeout(1500)
    print("edges before", p.locator(".react-flow__edge").count(), p.locator(".react-flow__edge").evaluate_all("els => els.map(e => e.dataset.id || e.getAttribute('data-testid'))"))
    btn = p.locator(".button-edge__button").first
    print("button html:", btn.evaluate("e => e.outerHTML")[:300])
    sent.clear(); msgs.clear()
    btn.evaluate("e => e.click()")
    p.wait_for_timeout(1500)
    print("edges after JS click", p.locator(".react-flow__edge").count())
    print("ws sent:", sent[:5])
    print("console:", [m for m in msgs if 'Hey developer' not in m][:10])
    # pointer click at the button center
    bb = btn.bounding_box()
    sent.clear(); msgs.clear()
    p.mouse.click(bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2)
    p.wait_for_timeout(1500)
    print("edges after mouse click", p.locator(".react-flow__edge").count())
    print("ws sent:", sent[:5])
    print("console:", msgs[:10])
    print("elementFromPoint:", p.evaluate("([x,y]) => document.elementFromPoint(x,y)?.outerHTML?.slice(0,200)", [bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2]))
    b.close()
