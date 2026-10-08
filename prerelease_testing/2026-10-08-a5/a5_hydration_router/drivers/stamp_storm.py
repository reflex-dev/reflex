"""a3_hydration: N tabs of src/syncstamp load PATH concurrently in one browser context (session restore).
Reports per-tab storage events / update_vars_internal sends, final values, frames per 5 s window afterwards.
Usage: stamp_storm.py BASE PATH NTABS OUT_JSON [OBSERVE_S=10]
"""
import asyncio
import json
import sys
import time

from playwright.async_api import async_playwright

assert "/envs/driver/" in sys.executable, sys.executable
CHROMIUM = "/opt/pw-browsers/chromium"
BASE, PATH, N, OUT = sys.argv[1].rstrip("/"), sys.argv[2], int(sys.argv[3]), sys.argv[4]
OBS = int(sys.argv[5]) if len(sys.argv) > 5 else 10
LOGGER = """() => { window.__se = []; window.addEventListener('storage', e => window.__se.length < 200 ? window.__se.push(
  [Math.round(performance.now()), e.key, e.oldValue, e.newValue]) : window.__se.push(0));
  window.__ws = {sent: 0, recv: 0, uvi: 0};
  const WS = window.WebSocket;
  window.WebSocket = function(...a) { const ws = new WS(...a);
    if (String(a[0]).includes('_event')) {
      const s = ws.send.bind(ws);
      ws.send = (d) => { window.__ws.sent++; if (typeof d === 'string' && d.includes('update_vars_internal')) window.__ws.uvi++; return s(d); };
      ws.addEventListener('message', () => { window.__ws.recv++; });
    }
    return ws; };
  window.WebSocket.prototype = WS.prototype; Object.assign(window.WebSocket, WS); }"""


async def hyd(page, t=30):
    for _ in range(t * 10):
        try:
            if await page.inner_text("#hyd-flag", timeout=200) == "H:yes":
                return True
        except Exception:
            pass
        await page.wait_for_timeout(100)
    return False


async def main():
    frames = []
    async with async_playwright() as pw:
        b = await pw.chromium.launch(executable_path=CHROMIUM)
        ctx = await b.new_context()
        await ctx.add_init_script(f"({LOGGER})()")
        # warm-up tab so the context has a value (a returning visitor)
        w = await ctx.new_page()
        await w.goto(BASE + "/")
        await hyd(w)
        await w.close()
        tabs = []
        for i in range(N):
            p = await ctx.new_page()

            tabs.append(p)
        await asyncio.gather(*[p.goto(BASE + PATH) for p in tabs])
        hyds = await asyncio.gather(*[hyd(p) for p in tabs])
        await tabs[0].wait_for_timeout(3000)
        async def total():
            t = 0
            for p in tabs:
                c = await p.evaluate("() => window.__ws")
                t += c["sent"] + c["recv"]
            return t
        windows = []
        for _ in range(max(OBS // 5, 1)):
            n0 = await total()
            await tabs[0].wait_for_timeout(5000)
            windows.append(await total() - n0)
        finals = [await p.inner_text("#theme") for p in tabs]
        se = [await p.evaluate("() => window.__se.length") for p in tabs]
        uvi = [(await p.evaluate("() => window.__ws"))["uvi"] for p in tabs]
        frames_total = await total()
        res = {"path": PATH, "n": N, "hydrated": hyds, "finals": finals,
               "ls_final": await tabs[0].evaluate("() => localStorage.getItem('ss_last')"),
               "converged": len(set(finals)) == 1, "storage_events": se, "uvi": uvi,
               "frames_total": frames_total, "windows_5s": windows, "storm": windows[-1] > 50}
        await b.close()
    print(json.dumps({k: res[k] for k in ("path", "n", "converged", "storm", "windows_5s", "frames_total", "finals", "storage_events")}))
    json.dump(res, open(OUT, "w"), indent=1)


asyncio.run(main())
