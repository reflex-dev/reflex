"""Measure initial JS/CSS bytes transferred for pages of the bpapp app.

Usage: python measure_bytes.py <base_url> <out_json> <label>
"""

import json
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
OUT = sys.argv[2]
LABEL = sys.argv[3]

PAGES = ["/app/", "/app/about", "/app/components"]
res = {"label": LABEL, "pages": {}}

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for path in PAGES:
        ctx = browser.new_context()
        page = ctx.new_page()
        recs = []

        def on_resp(r, recs=recs):
            try:
                body = r.body()
            except Exception:  # noqa: BLE001
                body = b""
            recs.append({
                "url": r.url,
                "status": r.status,
                "bytes": len(body),
                "enc": r.headers.get("content-encoding"),
                "ct": (r.headers.get("content-type") or "")[:40],
            })

        page.on("response", on_resp)
        page.goto(BASE + path, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(2500)
        js = [r for r in recs if ".js" in r["url"] and r["status"] < 400]
        css = [r for r in recs if ".css" in r["url"] and r["status"] < 400]
        res["pages"][path] = {
            "n_requests": len(recs),
            "n_js": len(js),
            "js_bytes": sum(r["bytes"] for r in js),
            "n_css": len(css),
            "css_bytes": sum(r["bytes"] for r in css),
            "total_bytes": sum(r["bytes"] for r in recs if r["status"] < 400),
            "gzip_responses": sum(1 for r in recs if r["enc"] == "gzip"),
            "js_urls": sorted(r["url"].rsplit("/", 1)[-1] for r in js),
        }
        ctx.close()
    browser.close()

with open(OUT, "w") as f:
    json.dump(res, f, indent=2)
for p, v in res["pages"].items():
    print(f'{LABEL} {p}: js={v["n_js"]} files {v["js_bytes"]}B css={v["css_bytes"]}B total={v["total_bytes"]}B gzip_resp={v["gzip_responses"]}/{v["n_requests"]}')
