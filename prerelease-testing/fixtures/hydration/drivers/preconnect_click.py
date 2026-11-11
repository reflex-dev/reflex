"""Click before the websocket connects: hold the backend socket for HOLD_MS via route_web_socket.

Usage: preconnect_click.py <base_url> <label> <out_json> [hold_ms]
Records the order in which the backend processed the click vs the page's on_load (cf_log).
"""

import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright

CHROMIUM = "/opt/pw-browsers/chromium"


async def run_once(browser, base: str, hold_ms: int) -> dict:
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
    await page.goto(base + "/clickfast")
    await page.wait_for_selector("#cf-always", timeout=15000)
    await page.wait_for_timeout(300)
    flag = await page.inner_text("#hyd-flag")
    connected_before_click = any(d == "out" and m.startswith("40") for d, m in frames)
    await page.click("#cf-always")
    # wait for hydration and the on_load
    for _ in range(150):
        try:
            if (await page.inner_text("#hyd-flag")) == "H:yes" and "load" in (await page.inner_text("#cf-log")):
                break
        except Exception:  # noqa: BLE001
            pass
        await page.wait_for_timeout(100)
    await page.wait_for_timeout(1500)
    log = json.loads(await page.inner_text("#cf-log"))
    sent = [m[:160] for d, m in frames if d == "out" and m.startswith("4")]
    await ctx.close()
    return {"flag_at_click": flag, "socket_connected_before_click": connected_before_click, "cf_log": log, "sent": sent, "console_errors": [c for c in console if c.startswith(("error", "warning"))]}


async def main():
    base, label, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    hold = int(sys.argv[4]) if len(sys.argv) > 4 else 2500
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(executable_path=CHROMIUM)
        runs = [await run_once(browser, base, hold) for _ in range(3)]
        await browser.close()
    out.write_text(json.dumps({"label": label, "hold_ms": hold, "runs": runs}, indent=1))
    for r in runs:
        print(label, r["flag_at_click"], "connected_before_click=", r["socket_connected_before_click"], r["cf_log"])


asyncio.run(main())
