"""N-004 e2e: start (new) or resume (by token) a session on c4e2e /misc, record values on arrival, bump, record again.
Usage: NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python drive_resume.py <base> <tokfile> new|resume <label>"""
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

assert "/envs/driver/" in sys.executable, sys.executable
base, tokfile, mode, label = sys.argv[1].rstrip("/"), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
console = []
IDS = ("limit", "items", "total", "mval")
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    if mode == "resume":
        ctx.add_init_script(f"window.sessionStorage.setItem('token', {json.dumps(tokfile.read_text().strip())});")
    page = ctx.new_page()
    page.on("console", lambda m: console.append(f"{m.type}: {m.text[:200]}") if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: console.append(f"PAGEERROR {str(e)[:200]}"))
    page.goto(base + "/misc", wait_until="networkidle", timeout=180000)
    page.wait_for_function("() => document.querySelector('#hyd')?.textContent === 'H:yes'", timeout=60000)
    time.sleep(1.5)
    arrival = {i: page.inner_text(f"#{i}") for i in IDS}
    page.click("#bump")
    page.click("#mbump")
    time.sleep(2)
    after = {i: page.inner_text(f"#{i}") for i in IDS}
    tok = page.evaluate("() => sessionStorage.getItem('token')")
    if mode == "new":
        tokfile.write_text(tok)
    b.close()
print(json.dumps({"label": label, "mode": mode, "token": tok, "arrival": arrival, "after_bump": after, "console": console}))
