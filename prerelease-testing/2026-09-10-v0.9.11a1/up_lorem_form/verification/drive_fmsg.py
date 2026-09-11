"""Drive the 5 fmsg variants: does the page render, does submit work, what console errors."""

import json
import pathlib
import sys
import time

from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
OUT = pathlib.Path(sys.argv[2])
LABEL = sys.argv[3]
OUT.mkdir(parents=True, exist_ok=True)

PAGES = ["unnamed", "named", "msgname", "nomsg", "msgtop", "labelonly", "controlonly"]
ERR_TEXT = "An error occurred while rendering this page."

results = []
console = []
page_errors = []
bad = []


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        page.on(
            "console",
            lambda m: console.append({"type": m.type, "text": m.text[:1200], "url": page.url}),
        )
        page.on("pageerror", lambda e: page_errors.append({"err": str(e)[:1200], "url": page.url}))
        page.on(
            "response",
            lambda r: bad.append({"url": r.url, "status": r.status})
            if r.status >= 400
            else None,
        )
        for name in PAGES:
            url = f"{BASE}/{name}"
            page.goto(url, wait_until="load", timeout=60000)
            time.sleep(3.5)
            body = page.inner_text("body")
            eb = ERR_TEXT in body
            heading = page.locator("#hd").count() > 0
            inp = page.locator("#inp").count() > 0
            page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
            results.append(
                {
                    "name": f"{name}_renders",
                    "status": "fail" if (eb or not heading or not inp) else "pass",
                    "details": f"error_boundary={eb} heading={heading} input={inp} body0={body[:90]!r}",
                }
            )
            if eb or not inp:
                results.append(
                    {"name": f"{name}_submit", "status": "skipped", "details": "page did not render"}
                )
                continue
            # empty submit -> should show validation message, not submit
            page.click("#sub")
            time.sleep(1.5)
            after_empty = page.inner_text("body")
            msg_shown = "This field is required." in after_empty
            page.fill("#inp", "alice")
            page.click("#sub")
            time.sleep(2.0)
            out = page.locator("#out").inner_text() if page.locator("#out").count() else ""
            results.append(
                {
                    "name": f"{name}_submit",
                    "status": "pass" if "alice" in out else "fail",
                    "details": f"state_out={out[:120]!r} empty_submit_msg_shown={msg_shown}",
                }
            )
        ctx.close()
        browser.close()


try:
    main()
finally:
    errs = [c for c in console if c["type"] == "error"]
    results.append(
        {
            "name": "console_errors",
            "status": "anomaly" if errs else "pass",
            "details": f"{len(errs)} error(s)",
        }
    )
    (OUT / "results.json").write_text(json.dumps(results, indent=2))
    (OUT / "console.json").write_text(json.dumps(console, indent=2))
    (OUT / "page_errors.json").write_text(json.dumps(page_errors, indent=2))
    (OUT / "bad_responses.json").write_text(json.dumps(bad, indent=2))
    print(f"== {LABEL} ==")
    for r in results:
        print(f"  {r['status']:8} {r['name']}: {r['details']}")
    for e in errs:
        print("  CONSOLE ERROR:", e["url"], "|", e["text"][:300].replace("\n", " "))
