"""Check that a dynamic route renders in a browser despite the 404 status line."""

import json
import sys

from playwright.sync_api import sync_playwright

base, out, label = sys.argv[1], sys.argv[2], sys.argv[3]
import pathlib

pathlib.Path(out).mkdir(parents=True, exist_ok=True)
results, console, bad = [], [], []

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    page = ctx.new_page()
    page.on("console", lambda m: console.append({"type": m.type, "text": m.text}))
    page.on(
        "response",
        lambda r: bad.append({"url": r.url, "status": r.status})
        if r.status >= 400
        else None,
    )
    for route, expect in [("/", "home"), ("/static-page/", "staticpage"), ("/item/42", "item-page")]:
        resp = page.goto(base + route, wait_until="load")
        status = resp.status if resp else None
        try:
            page.wait_for_selector("#marker", timeout=15000)
            marker = page.text_content("#marker")
        except Exception as e:  # noqa: BLE001
            marker = f"ERROR: {e}"
        path_txt = None
        if route.startswith("/item"):
            try:
                page.wait_for_function(
                    "() => document.querySelector('#path') && document.querySelector('#path').textContent.length > 0",
                    timeout=15000,
                )
                path_txt = page.text_content("#path")
            except Exception as e:  # noqa: BLE001
                path_txt = f"ERROR: {e}"
        results.append(
            {
                "route": route,
                "document_status": status,
                "marker": marker,
                "rendered_ok": marker == expect,
                "state_path_var": path_txt,
            }
        )
        page.screenshot(path=f"{out}/{route.strip('/').replace('/', '_') or 'index'}.png")
    ctx.close()
    b.close()

(pathlib.Path(out) / "results.json").write_text(json.dumps(results, indent=2))
(pathlib.Path(out) / "console.json").write_text(json.dumps(console, indent=2))
(pathlib.Path(out) / "bad_responses.json").write_text(json.dumps(bad, indent=2))
print(label, json.dumps(results, indent=2))
