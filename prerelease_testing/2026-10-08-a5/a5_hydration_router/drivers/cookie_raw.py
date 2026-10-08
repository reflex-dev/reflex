"""a3_hydration: does the boot rewrite raw cookie / localStorage values set outside reflex?
Sets raw values (as a server Set-Cookie or another script would), reloads, reports raw document.cookie / localStorage.
Usage: cookie_raw.py BASE OUT_JSON   (src/bootecho: be_ck cookie, be_note localStorage)
"""
import json
import sys

from playwright.sync_api import sync_playwright

assert "/envs/driver/" in sys.executable, sys.executable
BASE, OUT = sys.argv[1].rstrip("/"), sys.argv[2]
res = {}
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for raw in ['{"a":1}', "%41BC", "plain-value"]:
        ctx = b.new_context()
        p = ctx.new_page()
        p.goto(BASE + "/")
        p.wait_for_selector("#hyd-flag:has-text('H:yes')")
        ctx.add_cookies([{"name": "be_ck", "value": raw, "url": BASE + "/"}])
        p.reload()
        p.wait_for_selector("#hyd-flag:has-text('H:yes')")
        p.wait_for_timeout(1500)
        res[raw] = {"shown": p.inner_text("#ck"), "raw_after": [c["value"] for c in ctx.cookies() if c["name"] == "be_ck"],
                    "expires_after": [c["expires"] for c in ctx.cookies() if c["name"] == "be_ck"]}
        print(json.dumps({raw: res[raw]}))
        ctx.close()
    b.close()
json.dump(res, open(OUT, "w"), indent=1)
