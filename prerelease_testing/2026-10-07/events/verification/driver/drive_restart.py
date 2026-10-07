#!/usr/bin/env python
"""Durability probe (disk state manager): is a failed event's in-memory mutation persisted?

For each variant: fresh browser context -> hydrate -> a SUCCESSFUL control event (sets `other`) ->
the FAILING event (`direct_raise` sets `status` then raises) -> graceful server restart (SIGTERM via
bin/stop.sh, then bin/start.sh) -> reload the SAME tab (same token) -> read the displayed state.

  variant gap   : failing event 3 s after the control event (debounced disk write already flushed)
  variant fast  : failing event 0.3 s after the control event, server stopped 0.4 s later (inside the
                  2 s disk write debounce window; the queued item references the same in-memory object)

usage: drive_restart.py <venv> <dev|prod> <disk> <out.json>
"""

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

assert "/envs/driver" in sys.prefix, sys.prefix
sys.path.insert(0, str(Path(__file__).parent))
from drive_verify import INIT_JS, snap, wait_hydrated  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

SB = "/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad"
W = f"{SB}/apps/verify_events_0"


def sh(cmd: str, timeout=420):
    r = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=timeout)
    return (r.stdout + r.stderr).strip()


async def variant(browser, base, venv, mode, sm, name, gap, stop_delay, signal="TERM"):
    label = f"{venv}_{mode}_{sm}"
    ctx = await browser.new_context(viewport={"width": 1280, "height": 1300})
    await ctx.add_init_script(INIT_JS)
    page = await ctx.new_page()
    out = {"variant": name, "gap_s": gap, "stop_delay_s": stop_delay, "signal": signal}
    await page.goto(base + "/", wait_until="domcontentloaded")
    await wait_hydrated(page)
    await asyncio.sleep(2.5)  # let the hydrate write flush (debounce) so the control starts from a clean queue
    out["before"] = await snap(page)
    await page.click("#btn-sup_split_b", timeout=20000)  # control: successful event, sets other='b-ran'
    await asyncio.sleep(gap)
    await page.click("#btn-direct_raise", timeout=20000)  # status='direct-partial' then raise
    await asyncio.sleep(stop_delay)
    out["browser_after_fail"] = await snap(page)
    if signal == "TERM":
        out["stop"] = sh(f"bash {W}/bin/stop.sh {label}")
    else:
        pid = int(Path(f"{W}/pids/{label}.pid").read_text())
        sh(f"kill -KILL -- -{pid}")
        time.sleep(1)
        out["stop"] = sh(f"bash {W}/bin/stop.sh {label}")
    out["start"] = sh(f"bash {W}/bin/start.sh {venv} {mode} {sm} && sleep 8 && bash {W}/bin/wait_up.sh {mode} 400")
    await asyncio.sleep(1.0)
    await page.reload(wait_until="domcontentloaded")
    await wait_hydrated(page, timeout=120)
    await asyncio.sleep(1.0)
    out["after_restart_reload"] = await snap(page)
    await ctx.close()
    return out


async def main():
    venv, mode, sm, outp = sys.argv[1:5]
    base = "http://localhost:8641" if mode == "prod" else "http://localhost:3640"
    res = {"venv": venv, "mode": mode, "sm": sm, "variants": []}
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium", headless=True)
        for name, gap, stop_delay, sig in [("gap", 3.0, 3.0, "TERM"), ("fast", 0.3, 0.4, "TERM"), ("fast_kill9", 0.3, 0.4, "KILL")]:
            r = await variant(browser, base, venv, mode, sm, name, gap, stop_delay, sig)
            res["variants"].append(r)
            b, a = r["browser_after_fail"], r["after_restart_reload"]
            print(
                f"[{venv} {mode} {sm}] {name:10s} browser after fail: status={b['v-status']!r} other={b['v-other']!r} | "
                f"after restart+reload: status={a['v-status']!r} other={a['v-other']!r}",
                flush=True,
            )
            Path(outp).write_text(json.dumps(res, indent=1))
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
