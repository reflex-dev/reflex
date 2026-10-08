import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        ctx = await b.new_context(); p = await ctx.new_page(); got = []
        p.on("console", lambda m: got.append([m.type, m.text]) if m.type in ("error", "warning") else None)
        p.on("pageerror", lambda e: got.append(["pageerror", str(e)]))
        await p.goto("data:text/html,<script>console.error('E1');console.warn('W1');setTimeout(()=>{throw new Error('T1')},10)</script>")
        await p.wait_for_timeout(300); print(got); await b.close()
asyncio.run(main())
