"""Drive apps/lateapp. Usage: NO_PROXY=... $SB/envs/driver/bin/python drive_late.py <base> <out.json>"""
import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

assert f"/envs/{os.environ.get('DRIVER', 'driver')}/" in sys.executable, sys.executable  # playwright venv ($DRIVER)
base, out = sys.argv[1].rstrip("/"), sys.argv[2]
console, bad = [], []
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=os.environ.get("CHROMIUM", "/opt/pw-browsers/chromium"))
    p = b.new_page()
    p.on("console", lambda m: console.append(f"{m.type}: {m.text[:300]}"))
    p.on("pageerror", lambda e: console.append(f"PAGEERROR: {str(e)[:300]}"))
    p.on("response", lambda r: bad.append(f"{r.status} {r.url}") if r.status >= 400 else None)
    p.goto(base + "/", wait_until="networkidle", timeout=240000)
    p.wait_for_function("() => document.querySelector('#hyd')?.textContent === 'H:yes'", timeout=90000)
    time.sleep(1)
    p.click("#late_show")
    time.sleep(1.5)
    res = {i: p.inner_text(f"#{i}") for i in ("late_opts", "late_field_opts", "late_regs", "late_cfg")}
    p.screenshot(path=out.replace(".json", ".png"), full_page=True)
    b.close()
res["console"] = [c for c in console if "Hey developer" not in c and "[vite]" not in c and "DevTools" not in c]
res["bad"] = bad
open(out, "w").write(json.dumps(res, indent=1))
print(json.dumps(res, indent=1))
