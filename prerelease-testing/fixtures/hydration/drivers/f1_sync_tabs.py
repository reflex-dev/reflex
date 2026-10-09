"""F1 verifier: sync=True LocalStorage across two tabs on first load.

Part 1: tab A loads (fresh context) and logs `storage` events + its outgoing frames; tab B (same context) loads.
Part 2: tab B2 loads with its /_event websocket held HOLD_MS (Playwright route_web_socket); once B2 has mounted,
        tab A changes the synced var (button #set-sync-a). After B2 connects, compare values in A, B2, localStorage.
Usage: f1_sync_tabs.py BASE OUT_JSON [HOLD_MS]
"""
import asyncio
import json
import sys

from playwright.async_api import async_playwright

import os  # noqa: E402
assert f"/envs/{os.environ.get('DRV_VENV', 'driver')}/" in sys.executable, sys.executable
CHROMIUM = "/opt/pw-browsers/chromium"
LOGGER = """() => { window.__se = []; window.addEventListener('storage', e => window.__se.push(
  [Math.round(performance.now()), e.key, e.oldValue, e.newValue])); }"""


def rec(page, tag, frames):
    def on_ws(ws):
        if "_event" not in ws.url:
            return
        ws.on("framesent", lambda p: frames.append((tag, "out", p if isinstance(p, str) else "<bin>")))
        ws.on("framereceived", lambda p: frames.append((tag, "in", p if isinstance(p, str) else "<bin>")))
    page.on("websocket", on_ws)


async def hydrated(page, timeout_s=20):
    for _ in range(int(timeout_s * 10)):
        try:
            if await page.inner_text("#hyd-flag", timeout=200) == "H:yes":
                return True
        except Exception:  # noqa: BLE001
            pass
        await page.wait_for_timeout(100)
    return False


def sync_frames(frames, tag):
    out = []
    for t, d, p in frames:
        if t != tag:
            continue
        if "update_vars_internal" in p or "wu_sync" in p:
            out.append(f"{d}: {p[:400]}")
    return out


async def main():
    base, out = sys.argv[1], sys.argv[2]
    hold = int(sys.argv[3]) if len(sys.argv) > 3 else 1500
    res = {}
    frames = []
    async with async_playwright() as pw:
        b = await pw.chromium.launch(executable_path=CHROMIUM)
        ctx = await b.new_context()
        A = await ctx.new_page()
        rec(A, "A", frames)
        await A.goto(base)
        res["A_hydrated"] = await hydrated(A)
        await A.evaluate(LOGGER)
        res["ls_after_A"] = await A.evaluate("() => localStorage.getItem('wu_sync')")
        # Part 1
        B = await ctx.new_page()
        rec(B, "B", frames)
        await B.goto(base)
        res["B_hydrated"] = await hydrated(B)
        await B.wait_for_timeout(1500)
        res["p1_A_storage_events"] = await A.evaluate("() => window.__se")
        res["p1_A_sync_frames"] = sync_frames(frames, "A")
        res["p1_A_shown"] = await A.inner_text("#wu-sync")
        res["p1_B_shown"] = await B.inner_text("#wu-sync")
        res["p1_ls"] = await A.evaluate("() => localStorage.getItem('wu_sync')")
        await B.close()
        # Part 2
        await A.evaluate("() => { window.__se = []; }")
        n_a = len(frames)
        B2 = await ctx.new_page()
        rec(B2, "B2", frames)

        async def handler(ws):
            if "_event" not in ws.url:
                ws.connect_to_server()
                return
            await asyncio.sleep(hold / 1000)
            server = ws.connect_to_server()
            ws.on_message(lambda m: server.send(m))
            server.on_message(lambda m: ws.send(m))

        await B2.route_web_socket("**/_event/**", handler)
        await B2.goto(base)
        await B2.wait_for_selector("#wu-sync", timeout=15000)
        await B2.wait_for_timeout(200)  # B2 mounted: its boot auth (storage vars) is already captured
        await A.click("#set-sync-a")
        for _ in range(40):  # wait until A's change has landed in localStorage (while B2 is still held)
            if await A.evaluate("() => localStorage.getItem('wu_sync')") == "sync-from-tabA":
                break
            await A.wait_for_timeout(50)
        res["p2_B2_connected_before_A_change"] = any(t == "B2" and d == "out" and p.startswith("40") for t, d, p in frames)
        res["p2_ls_after_A_click"] = await A.evaluate("() => localStorage.getItem('wu_sync')")
        res["p2_A_shown_after_click"] = await A.inner_text("#wu-sync")
        res["p2_B2_hydrated"] = await hydrated(B2)
        await B2.wait_for_timeout(2500)
        res["p2_A_storage_events"] = await A.evaluate("() => window.__se")
        res["p2_A_shown_final"] = await A.inner_text("#wu-sync")
        res["p2_B2_shown_final"] = await B2.inner_text("#wu-sync")
        res["p2_ls_final"] = await A.evaluate("() => localStorage.getItem('wu_sync')")
        res["p2_A_sync_frames"] = sync_frames(frames[n_a:], "A")
        res["p2_B2_sync_frames"] = sync_frames(frames, "B2")
        await b.close()
    with open(out, "w") as f:
        json.dump(res, f, indent=1)
    for k, v in res.items():
        print(k, "=", json.dumps(v)[:1500])


asyncio.run(main())
