"""Trace 3 tabs loading /stamp concurrently: storage events, websocket frames, final display. Usage: stamp_trace.py BASE N"""
import asyncio, json, sys, time
from playwright.async_api import async_playwright
assert "/envs/driver/" in sys.executable
BASE, N = sys.argv[1].rstrip("/"), int(sys.argv[2])
T0 = time.time()
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        ctx = await b.new_context()
        log = []
        pages = []
        for i in range(N):
            pg = await ctx.new_page()
            tag = f"t{i}"
            await pg.add_init_script("() => {}")
            pg.on("websocket", lambda ws, tag=tag: (
                ws.on("framesent", lambda f, tag=tag: log.append((round(time.time()-T0, 3), tag, "out", str(f)[:160]))),
                ws.on("framereceived", lambda f, tag=tag: log.append((round(time.time()-T0, 3), tag, "in", str(f)[:220])))))
            await pg.add_init_script("""window.addEventListener('storage', e => (window.__se ??= []).push([Math.round(performance.now()), e.key, e.oldValue, e.newValue]));""")
            pages.append(pg)
        await asyncio.gather(*(pg.goto(BASE + "/stamp") for pg in pages))
        await asyncio.sleep(4)
        for i, pg in enumerate(pages):
            print(f"t{i} final display:", await pg.locator("#theme").inner_text(), " storage events:", await pg.evaluate("window.__se"))
        print("localStorage:", await pages[0].evaluate("localStorage.getItem('ss_last')"))
        for e in log:
            if "ss_last" in e[3] or "last_rx_state_" in e[3] or "update_vars" in e[3] or "on_load" in e[3]:
                print(e)
        await b.close()
asyncio.run(main())
