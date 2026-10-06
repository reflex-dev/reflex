"""Ad-hoc DOM exploration for the data editor page."""
import json
import os
import sys

import playwright

assert "/scratchpad/envs/driver/" in playwright.__file__, playwright.__file__
from playwright.sync_api import sync_playwright  # noqa: E402

base, path = sys.argv[1], sys.argv[2]
js = sys.argv[3] if len(sys.argv) > 3 else None
with sync_playwright() as p:
    proxy = os.environ.get("HTTPS_PROXY")
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", proxy={"server": proxy, "bypass": "localhost,127.0.0.1"} if proxy else None)
    pg = b.new_page(viewport={"width": 1280, "height": 900})
    msgs = []
    pg.on("console", lambda m: msgs.append(f"{m.type}: {m.text[:300]}"))
    pg.on("pageerror", lambda e: msgs.append(f"PAGEERROR: {str(e)[:300]}"))
    pg.goto(base + path, wait_until="domcontentloaded", timeout=120000)
    pg.wait_for_timeout(int(os.environ.get("SETTLE", "8000")))
    if js:
        print(json.dumps(pg.evaluate(js), indent=1, default=str)[:12000])
    print("---- console (%d)" % len(msgs))
    seen = {}
    for m in msgs:
        seen[m] = seen.get(m, 0) + 1
    for m, c in list(seen.items())[:40]:
        print(f"x{c} {m}")
    b.close()
