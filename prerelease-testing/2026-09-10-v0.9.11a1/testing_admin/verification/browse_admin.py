"""Open the backend /admin pages in Chromium and record status + a screenshot."""

import json
import sys

from playwright.sync_api import sync_playwright

base = sys.argv[1]
outdir = sys.argv[2]
res = {"base": base, "pages": []}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-proxy-server"])
    page = b.new_page()
    console = []
    page.on("console", lambda m: console.append(f"{m.type}:{m.text}"))
    for path, name in (("/admin/", "admin_index"), ("/admin/widget/list", "admin_list")):
        r = page.goto(base + path, wait_until="load")
        page.screenshot(path=f"{outdir}/{name}.png")
        res["pages"].append(
            {
                "path": path,
                "status": r.status if r else None,
                "body_text": page.inner_text("body")[:200],
            }
        )
    res["console"] = console
    b.close()
print(json.dumps(res, indent=2))
