"""Prod multi-worker probe: does an OIDC login complete, and what do the /_reflex/cookies/sync POSTs return?

Usage: prod_sync_probe.py <base> <label> [N]
Each attempt: fresh browser context -> /dashboard -> login as alice -> wait up to 20 s for "Alice Admin".
Records every /_reflex/cookies/sync response status, the final URL and console errors.
"""

import json
import re
import sys
import time

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import CHROMIUM, W, attach, login  # noqa: E402

BASE = sys.argv[1].rstrip("/")
LABEL = sys.argv[2]
N = int(sys.argv[3]) if len(sys.argv) > 3 else 4
out = []
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM)
    for i in range(N):
        ctx = browser.new_context()
        page = ctx.new_page()
        page.set_default_timeout(30_000)
        diag = {}
        attach(page, diag)
        syncs = []
        page.on("response", lambda r: syncs.append(r.status) if "/_reflex/cookies/sync" in r.url else None)
        t0 = time.time()
        page.goto(BASE + "/dashboard")
        page.wait_for_url(re.compile("/login"))
        login(page, "alice")
        ok = False
        for _ in range(40):
            page.wait_for_timeout(500)
            if page.locator("#user-name").count() and page.locator("#user-name").inner_text() == "Alice Admin":
                ok = True
                break
        rec = {"i": i, "login_ok": ok, "secs": round(time.time() - t0, 1), "final_url": page.url.replace(BASE, ""),
               "sync_statuses": syncs, "cookies": sorted(c["name"] for c in ctx.cookies() if c["name"].startswith("_oidc")),
               "console_errors": [c["text"][:100] for c in diag.get("console", []) if c["type"] == "error" and "8358" not in c["url"]][:4]}
        if not ok:
            page.screenshot(path=str(W / "screenshots" / f"{LABEL}-prodsync-{i}.png"))
        out.append(rec)
        print(json.dumps(rec), flush=True)
        ctx.close()
    browser.close()
(W / "logs" / f"prodsync-{LABEL}.json").write_text(json.dumps(out, indent=2))
print("LOGIN_OK", sum(r["login_ok"] for r in out), "/", len(out))
