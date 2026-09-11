"""Drive the frontend_path app served under a sub-path.

Usage: python drive_fp.py <port> <out.json>
"""

import json
import sys

from playwright.sync_api import sync_playwright

PORT, OUT = int(sys.argv[1]), sys.argv[2]
BASE = f"http://localhost:{PORT}"
R = {"steps": [], "console": [], "pageerrors": [], "failed": [], "http_errors": []}


def step(n, **kw):
    """Record a step."""
    R["steps"].append({"step": n, **kw})
    print(f"[{n}] " + json.dumps(kw, default=str)[:300], flush=True)


def txt(page, sel):
    """Read text or a marker."""
    try:
        return page.locator(sel).first.inner_text(timeout=4000)
    except Exception as e:  # noqa: BLE001
        return f"<absent:{type(e).__name__}>"


with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
    page = br.new_context().new_page()
    page.on("console", lambda m: R["console"].append({"type": m.type, "text": m.text[:250]}))
    page.on("pageerror", lambda e: R["pageerrors"].append(str(e)[:250]))
    page.on("requestfailed", lambda r: R["failed"].append({"url": r.url[:150], "err": str(r.failure)[:100]}))
    page.on("response", lambda r: R["http_errors"].append({"url": r.url[:150], "status": r.status})
            if r.status >= 400 else None)

    page.goto(f"{BASE}/myapp/", wait_until="networkidle")
    page.wait_for_timeout(3000)
    step("load", url=page.url, count=txt(page, "#count"), doubled=txt(page, "#doubled"),
         body=page.locator("body").inner_text()[:150])

    page.click("#inc")
    page.wait_for_timeout(1200)
    page.click("#inc")
    page.wait_for_timeout(1200)
    step("after_two_clicks", count=txt(page, "#count"), doubled=txt(page, "#doubled"))

    page.click("#to-about")
    page.wait_for_timeout(2000)
    step("client_route_to_about", url=page.url, heading=txt(page, "#about-heading"))

    page.click("#to-home")
    page.wait_for_timeout(2000)
    step("back_home", url=page.url, count=txt(page, "#count"))

    page.reload(wait_until="networkidle")
    page.wait_for_timeout(2500)
    step("after_reload", url=page.url, count=txt(page, "#count"))

    # deep link straight to the sub-path route
    page.goto(f"{BASE}/myapp/about", wait_until="networkidle")
    page.wait_for_timeout(2500)
    step("deep_link_about", url=page.url, heading=txt(page, "#about-heading"),
         body=page.locator("body").inner_text()[:120])

    R["console_errors"] = [c for c in R["console"] if c["type"] == "error"]
    br.close()

with open(OUT, "w") as f:
    json.dump(R, f, indent=1)
print("CONSOLE ERRORS:", json.dumps(R["console_errors"])[:900])
print("PAGE ERRORS:", json.dumps(R["pageerrors"])[:600])
print("FAILED:", json.dumps(R["failed"])[:500])
print("HTTP>=400:", json.dumps(R["http_errors"])[:600])
print("saved", OUT)
