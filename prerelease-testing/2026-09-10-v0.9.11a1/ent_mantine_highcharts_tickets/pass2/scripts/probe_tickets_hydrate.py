"""Why does no button work on the tickets page? Watch the socket both ways."""
import sys, json, time
from playwright.sync_api import sync_playwright

BASE = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else None
sent, recv, console = [], [], []
with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
    page = br.new_context(viewport={"width": 1400, "height": 1000}).new_page()
    page.on("console", lambda m: console.append((m.type, m.text[:300])))
    page.on("websocket", lambda ws: (
        ws.on("framesent", lambda pl: sent.append(str(pl)[:1500])),
        ws.on("framereceived", lambda pl: recv.append(str(pl)[:1500])),
    ))
    page.goto(BASE, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(5000)
    print("--- after load: sent", len(sent), "recv", len(recv))
    for i, f in enumerate(sent):
        print(f"  SENT[{i}]", f[:700])
    for i, f in enumerate(recv):
        print(f"  RECV[{i}]", f[:900])
    n = len(sent)
    page.click("text=Seed")
    page.wait_for_timeout(3000)
    print("--- after clicking Seed: new sent frames", len(sent) - n)
    for f in sent[n:]:
        print("  SENT", f[:700])
    print("--- rows now:", page.locator("tbody tr").count(), "| badges:",
          page.locator(".rt-Badge").all_inner_texts()[:2])
    print("--- console:", json.dumps(console)[:1500])
    dispatchers = page.evaluate(
        "() => { const w = window; const keys = Object.keys(w).filter(k => /dispatch|state/i.test(k)); "
        "return {keys: keys.slice(0,20)}; }")
    print("--- window keys:", dispatchers)
    if OUT:
        open(OUT, "w").write(json.dumps({"sent": sent, "recv": recv, "console": console}, indent=1))
    br.close()
