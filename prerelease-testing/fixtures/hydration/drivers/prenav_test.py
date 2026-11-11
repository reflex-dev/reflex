"""Navigate client-side BEFORE the websocket connects (socket held HOLD_MS), from a page with a slow on_load.

Usage: prenav_test.py <base_url> <label> <out_json> [hold_ms]
Checks: the new page's on_load runs, the old page's slow on_load does not keep running, the page hydrates.
"""

import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright

CHROMIUM = "/opt/pw-browsers/chromium"


async def run_once(browser, base: str, hold_ms: int, start: str, target_nav: str, target_sel: str) -> dict:
    ctx = await browser.new_context()
    page = await ctx.new_page()
    frames: list = []
    console: list = []
    page.on("console", lambda m: console.append(f"{m.type}: {m.text[:200]}"))

    async def handler(ws):
        if "_event" not in ws.url:
            ws.connect_to_server()
            return
        await asyncio.sleep(hold_ms / 1000)
        server = ws.connect_to_server()

        def from_page(msg):
            frames.append(("out", msg if isinstance(msg, str) else "<bin>"))
            server.send(msg)

        def from_server(msg):
            frames.append(("in", msg if isinstance(msg, str) else "<bin>"))
            ws.send(msg)

        ws.on_message(from_page)
        server.on_message(from_server)

    await page.route_web_socket("**/_event/**", handler)
    await page.goto(base + start)
    await page.wait_for_selector(target_nav, timeout=15000)
    await page.wait_for_timeout(200)
    connected_before_nav = any(d == "out" and m.startswith("40") for d, m in frames)
    await page.click(target_nav)
    await page.wait_for_selector(target_sel, timeout=10000)
    hyd = None
    for _ in range(100):
        try:
            hyd = await page.inner_text("#hyd-flag")
            if hyd == "H:yes":
                break
        except Exception:  # noqa: BLE001
            pass
        await page.wait_for_timeout(100)
    await page.wait_for_timeout(7000)
    trace = json.loads(await page.inner_text("#trace"))
    res = {
        "url": page.url,
        "connected_before_nav": connected_before_nav,
        "hyd_after": hyd,
        "trace": trace,
        "sent": [m[:170] for d, m in frames if d == "out" and m.startswith("4")],
        "console_errors": [c for c in console if c.startswith(("error", "warning"))],
    }
    for sel in ("#other-count", "#slow-progress-other", "#item-trace"):
        try:
            res[sel] = await page.inner_text(sel, timeout=500)
        except Exception:  # noqa: BLE001
            pass
    await ctx.close()
    return res


async def main():
    base, label, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    hold = int(sys.argv[4]) if len(sys.argv) > 4 else 2000
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(executable_path=CHROMIUM)
        runs = {
            "slow_to_other": [await run_once(browser, base, hold, "/slow", "#nav-other", "#page-other") for _ in range(2)],
            "item1_to_item2": [await run_once(browser, base, hold, "/items/1", "#nav-item2", "#page-item") for _ in range(2)],
        }
        await browser.close()
    out.write_text(json.dumps({"label": label, "hold_ms": hold, "runs": runs}, indent=1))
    for k, rs in runs.items():
        for r in rs:
            print(label, k, "url=", r["url"].split("/", 3)[-1], "connected_before_nav=", r["connected_before_nav"], "hyd=", r["hyd_after"],
                  "trace=", r["trace"], {s: r.get(s) for s in ("#other-count", "#slow-progress-other", "#item-trace") if s in r})


asyncio.run(main())
