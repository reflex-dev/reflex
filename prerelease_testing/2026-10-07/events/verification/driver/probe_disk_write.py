#!/usr/bin/env python
"""Does a failed event's mutation ever reach the disk state manager's .pkl files, and when?

Scans the pickles in run/<venv>_<mode>/.states for the marker strings while driving the page.
(`reflex run` wipes .states at every start, so there is no cross-restart durability to test.)

usage: probe_disk_write.py <venv> <dev|prod>     (server must already be running with the disk manager)
"""

import asyncio
import json
import sys
import time
from pathlib import Path

assert "/envs/driver" in sys.prefix, sys.prefix
sys.path.insert(0, str(Path(__file__).parent))
from drive_verify import INIT_JS, snap, wait_hydrated  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

SB = "/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad"
W = f"{SB}/apps/verify_events_0"


async def main():
    venv, mode = sys.argv[1:3]
    base = "http://localhost:8641" if mode == "prod" else "http://localhost:3640"
    states = Path(f"{W}/run/{venv}_{mode}/.states")

    def on_disk(needle: str) -> bool:
        return any(needle.encode() in p.read_bytes() for p in states.glob("*.pkl"))

    res = {"venv": venv, "mode": mode, "steps": []}

    def rec(step, **kw):
        row = {"step": step, "t": round(time.time() - t0, 1), **kw}
        res["steps"].append(row)
        print(json.dumps(row), flush=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium", headless=True)
        ctx = await browser.new_context(viewport={"width": 1280, "height": 1300})
        await ctx.add_init_script(INIT_JS)
        page = await ctx.new_page()
        t0 = time.time()
        await page.goto(base + "/", wait_until="domcontentloaded")
        await wait_hydrated(page)
        await asyncio.sleep(3.0)
        rec("hydrated", pkl_files=len(list(states.glob("*.pkl"))), b_ran=on_disk("b-ran"), direct_partial=on_disk("direct-partial"))

        await page.click("#btn-sup_split_b")  # control: successful event -> other='b-ran'
        await asyncio.sleep(0.5)
        rec("control event +0.5s (inside 2 s debounce)", b_ran=on_disk("b-ran"))
        await asyncio.sleep(3.0)
        rec("control event +3.5s", b_ran=on_disk("b-ran"))

        await page.click("#btn-direct_raise")  # failing event -> status='direct-partial' in memory
        await asyncio.sleep(0.5)
        rec("failing event +0.5s", browser_status=(await snap(page))["v-status"], direct_partial=on_disk("direct-partial"))
        await asyncio.sleep(3.5)
        rec("failing event +4s (debounce long past)", browser_status=(await snap(page))["v-status"], direct_partial=on_disk("direct-partial"))
        await asyncio.sleep(8.0)
        rec("failing event +12s", direct_partial=on_disk("direct-partial"))

        await page.reload(wait_until="domcontentloaded")
        await wait_hydrated(page)
        await asyncio.sleep(0.5)
        rec("after reload (in-memory truth)", browser_status=(await snap(page))["v-status"], direct_partial=on_disk("direct-partial"))
        await asyncio.sleep(3.0)
        rec("reload +3.5s (hydrate wrote?)", direct_partial=on_disk("direct-partial"))

        await page.click("#btn-ping")  # next successful event -> set_state -> debounced write
        await asyncio.sleep(0.5)
        rec("ping +0.5s", direct_partial=on_disk("direct-partial"))
        await asyncio.sleep(3.0)
        rec("ping +3.5s", direct_partial=on_disk("direct-partial"))
        await browser.close()
    Path(sys.argv[3] if len(sys.argv) > 3 else f"{W}/out_extra/disk_write_{venv}_{mode}.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    asyncio.run(main())
