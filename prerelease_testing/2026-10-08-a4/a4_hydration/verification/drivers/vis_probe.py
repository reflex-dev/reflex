"""Probe: get real background tabs (document.visibilityState == 'hidden') in headful Chromium under Xvfb via
Target.createTarget(background=True, newWindow=False) on a browser CDP session."""
import asyncio
import sys

from playwright.async_api import async_playwright

assert "/scratchpad/envs/driver/" in sys.executable, sys.executable


async def main():
    async with async_playwright() as pw:
        ign = ["--disable-background-timer-throttling", "--disable-renderer-backgrounding", "--disable-backgrounding-occluded-windows"]
        b = await pw.chromium.launch(executable_path="/opt/pw-browsers/chromium", headless=False, ignore_default_args=ign)
        ctx = await b.new_context()
        t0 = await ctx.new_page()
        await t0.goto("http://localhost:3660/")
        ps = await ctx.new_cdp_session(t0)
        cid = (await ps.send("Target.getTargetInfo"))["targetInfo"]["browserContextId"]
        bs = await b.new_browser_cdp_session()
        pages = []
        for _ in range(2):
            async with ctx.expect_page() as pi:
                await bs.send("Target.createTarget", {"url": "about:blank", "browserContextId": cid, "background": True, "newWindow": False})
            pages.append(await pi.value)
        allp = [t0] + pages
        print("after create:", [await p.evaluate("document.visibilityState") for p in allp])
        await pages[0].goto("http://localhost:3660/")
        await asyncio.sleep(1)
        print("after goto in bg tab:", [await p.evaluate("document.visibilityState") for p in allp])
        print("timer rate in bg tab (setInterval 10ms for 1.5s):", await pages[0].evaluate("() => new Promise(r => { let n = 0; const i = setInterval(() => n++, 10); setTimeout(() => { clearInterval(i); r(n); }, 1500); })"))
        print("timer rate in fg tab:", await t0.evaluate("() => new Promise(r => { let n = 0; const i = setInterval(() => n++, 10); setTimeout(() => { clearInterval(i); r(n); }, 1500); })"))
        await b.close()


asyncio.run(main())
