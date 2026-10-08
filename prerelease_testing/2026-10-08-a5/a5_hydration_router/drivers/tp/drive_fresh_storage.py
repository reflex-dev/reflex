"""F-002 side-effect check on the third-party auth demos: what does a FRESH browser profile have in
localStorage / sessionStorage / cookies after the first page load (and after visiting more pages)?

Usage: drive_fresh_storage.py <base_url> <label> <out_json> <path> [<path> ...]
"""
import json
import sys

from tpdrive import Capture, browser

BASE = sys.argv[1].rstrip("/")
LABEL = sys.argv[2]
OUT = sys.argv[3]
PATHS = sys.argv[4:] or ["/"]
cap = Capture()
res = {"label": LABEL, "visits": []}
with browser() as b:
    ctx = b.new_context()
    page = cap.attach(ctx.new_page(), "main")
    for path in PATHS:
        page.goto(BASE + path, wait_until="networkidle")
        page.wait_for_timeout(2500)
        st = page.evaluate(
            """() => ({
              local: Object.fromEntries(Object.entries(localStorage)),
              session: Object.fromEntries(Object.entries(sessionStorage)),
              cookie: document.cookie,
            })"""
        )
        res["visits"].append({"path": path, "url": page.url, **st})
        print(f"{LABEL} {path} -> url={page.url.replace(BASE, '')} local={json.dumps(st['local'])[:300]} session={json.dumps(st['session'])[:200]} cookie={st['cookie'][:200]!r}")
    cookies = ctx.cookies()
    res["context_cookies"] = [{k: c[k] for k in ("name", "value", "expires")} for c in cookies]
    print(f"{LABEL} context cookies:", [(c['name'], c['value'][:40], c['expires']) for c in cookies])
cap.dump(OUT, res)
