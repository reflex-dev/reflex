import asyncio, sys
assert "/envs/driver" in sys.prefix, sys.prefix
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium", headless=True)
        page = await b.new_page()
        seen = []
        page.on("console", lambda m: seen.append(("console", m.type, m.text[:90], m.location.get("url") if hasattr(m, "location") and m.location else None)))
        page.on("response", lambda r: seen.append(("response", r.status, r.url)) if r.status >= 400 else None)
        await page.goto("http://localhost:8641/", wait_until="domcontentloaded")
        await asyncio.sleep(4)
        for s in seen: print(s)
        await b.close()
asyncio.run(main())
