"""Probe the tickets New Ticket form: does a controlled input's on_change reach the state?"""
import json, sys
from playwright.sync_api import sync_playwright
BASE = sys.argv[1]
MODE = sys.argv[2]  # "fill" or "type"
sent, recv, console, perr = [], [], [], []
with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
    pg = br.new_context(viewport={"width":1400,"height":1000}).new_page()
    pg.on("console", lambda m: console.append((m.type, m.text[:200])))
    pg.on("pageerror", lambda e: perr.append(str(e)[:300]))
    pg.on("websocket", lambda ws: (
        ws.on("framesent", lambda pl: sent.append(str(pl)[:600])),
        ws.on("framereceived", lambda pl: recv.append(str(pl)[:600])),
    ))
    pg.goto(BASE, wait_until="networkidle", timeout=60000); pg.wait_for_timeout(3000)
    rows0 = pg.locator("tbody tr").count()
    pg.click("text=New Ticket"); pg.wait_for_timeout(1200)
    n = len(sent)
    if MODE == "fill":
        pg.fill("input[placeholder='Title']", "QA manual ticket")
    else:
        pg.click("input[placeholder='Title']")
        pg.type("input[placeholder='Title']", "QA manual ticket", delay=40)
    pg.wait_for_timeout(2500)
    print(f"--- after {MODE} title: frames sent", len(sent)-n)
    for f in sent[n:]: print("  SENT", f[:300])
    print("  input value now:", pg.locator("input[placeholder='Title']").input_value())
    n2 = len(sent)
    pg.click("button:has-text('Create')"); pg.wait_for_timeout(2500)
    print("--- after Create: frames sent", len(sent)-n2)
    for f in sent[n2:]: print("  SENT", f[:300])
    rows1 = pg.locator("tbody tr").count()
    print("ROWS before/after:", rows0, rows1)
    print("form still open:", pg.locator("input[placeholder='Title']").count())
    print("console:", [c for c in console if c[0] in ("error","warning")])
    print("pageerrors:", perr)
    pg.screenshot(path=f"{sys.argv[3]}")
    br.close()
