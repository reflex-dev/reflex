"""a3_hydration: sync=True LocalStorage echo race + many-tab storm on src/bootecho (Prefs.theme, key be_theme).

Part R (race): tab A sets theme=v1. Tab B loads with its server->client websocket messages HELD for HOLD_MS
(Playwright route_web_socket; client->server passes through, so B's CONNECT carries vars be_theme=v1).
While B's deltas are held, A sets theme=v2. Then B's queue is released. Records A's storage events, A's
#theme timeline, update_vars_internal events sent by A and B, final values. A correct boot never makes A
show v1 again (no stale echo).
Part S (storm): tab0 + N tabs loading concurrently while tab0 changes theme 5 times (250 ms apart);
then checks convergence and that the websocket traffic goes quiet (no ping-pong).
Usage: sync_race.py BASE OUT_JSON [HOLD_MS] [N_TABS] [PARTS=RS] [OBSERVE_S=0]
"""
import asyncio
import json
import sys
import time

from playwright.async_api import async_playwright

import os  # noqa: E402
assert f"/envs/{os.environ.get('DRV_VENV', 'driver')}/" in sys.executable, sys.executable
CHROMIUM = "/opt/pw-browsers/chromium"
BASE = sys.argv[1].rstrip("/")
OUT = sys.argv[2]
HOLD = int(sys.argv[3]) if len(sys.argv) > 3 else 2500
NTABS = int(sys.argv[4]) if len(sys.argv) > 4 else 6
PARTS = sys.argv[5] if len(sys.argv) > 5 else "RS"
OBSERVE_S = int(sys.argv[6]) if len(sys.argv) > 6 else 0  # extra observation: frames per 5 s window
LOGGER = """() => { window.__se = []; window.addEventListener('storage', e => window.__se.push(
  [Math.round(performance.now()), e.key, e.oldValue, e.newValue])); }"""


async def hyd(page, t=30):
    for _ in range(t * 10):
        try:
            if await page.inner_text("#hyd-flag", timeout=200) == "H:yes":
                return True
        except Exception:
            pass
        await page.wait_for_timeout(100)
    return False


async def set_theme(page, v):
    await page.fill("#theme-in", v)
    await page.locator("#theme-in").blur()


def rec(page, tag, frames):
    def on_ws(ws):
        if "_event" not in ws.url:
            return
        ws.on("framesent", lambda p: frames.append((round(time.time(), 3), tag, "out", p if isinstance(p, str) else "<bin>")))
        ws.on("framereceived", lambda p: frames.append((round(time.time(), 3), tag, "in", p if isinstance(p, str) else "<bin>")))
    page.on("websocket", on_ws)


def uvi(frames, tag):
    return [f[3][:260] for f in frames if f[1] == tag and f[2] == "out" and "update_vars_internal" in f[3]]


async def watch_theme(page, timeline, stop):
    last = None
    while not stop.is_set():
        try:
            v = await page.inner_text("#theme", timeout=200)
            if v != last:
                timeline.append((round(time.time(), 3), v))
                last = v
        except Exception:
            pass
        await asyncio.sleep(0.02)


async def main():
    res = {}
    async with async_playwright() as pw:
        b = await pw.chromium.launch(executable_path=CHROMIUM)
        # ---- Part R
        await (part_r(b, res) if "R" in PARTS else asyncio.sleep(0))
        await (part_s(b, res) if "S" in PARTS else asyncio.sleep(0))
        await b.close()
    with open(OUT, "w") as f:
        json.dump(res, f, indent=1, default=str)


async def part_r(b, res):
    if True:
        ctx = await b.new_context()
        await ctx.add_init_script(f"({LOGGER})()")
        frames = []
        A = await ctx.new_page()
        rec(A, "A", frames)
        await A.goto(BASE + "/")
        await hyd(A)
        await set_theme(A, "v1")
        await A.wait_for_timeout(800)
        state = {"ws": None, "held": [], "released": False, "connect": []}

        async def handler(ws):
            server = ws.connect_to_server()
            state["ws"] = ws

            def c2s(m):
                if isinstance(m, str) and m.startswith("40/_event"):
                    state["connect"].append(m[:500])
                server.send(m)

            def s2c(m):
                if state["released"]:
                    ws.send(m)
                else:
                    state["held"].append(m)
            ws.on_message(c2s)
            server.on_message(s2c)

        B = await ctx.new_page()
        rec(B, "B", frames)
        await B.route_web_socket("**/_event/**", handler)
        await B.goto(BASE + "/")
        for _ in range(100):
            if state["connect"]:
                break
            await B.wait_for_timeout(50)
        await B.wait_for_timeout(300)
        stop = asyncio.Event()
        tl_a, tl_b = [], []
        wa = asyncio.create_task(watch_theme(A, tl_a, stop))
        wb = asyncio.create_task(watch_theme(B, tl_b, stop))
        t_change = round(time.time(), 3)
        await set_theme(A, "v2")
        await A.wait_for_timeout(HOLD)
        n_held = len(state["held"])
        t_release = round(time.time(), 3)
        state["released"] = True
        for m in state["held"]:
            state["ws"].send(m)
        await A.wait_for_timeout(3000)
        stop.set()
        await wa
        await wb
        res["R"] = {
            "hold_ms": HOLD, "b_connect": state["connect"], "n_held_msgs": n_held, "t_change": t_change, "t_release": t_release,
            "A_timeline": tl_a, "B_timeline": tl_b,
            "A_storage_events": await A.evaluate("() => window.__se"),
            "B_storage_events": await B.evaluate("() => window.__se"),
            "A_uvi": uvi(frames, "A"), "B_uvi": uvi(frames, "B"),
            "A_final": await A.inner_text("#theme"), "B_final": await B.inner_text("#theme"),
            "ls_final": await A.evaluate("() => localStorage.getItem('be_theme')"),
            "A_showed_v1_after_change": any(v == "v1" and t > t_change + 0.05 for t, v in tl_a),
        }
        r = res["R"]
        print("R:", json.dumps({k: r[k] for k in ("n_held_msgs", "A_timeline", "A_final", "B_final", "ls_final", "A_showed_v1_after_change")}))
        print("   A storage events:", r["A_storage_events"])
        print("   B storage events:", r["B_storage_events"])
        print("   A uvi:", len(r["A_uvi"]), " B uvi:", len(r["B_uvi"]))
        await ctx.close()



async def part_s(b, res):
    if True:
        ctx = await b.new_context()
        await ctx.add_init_script(f"({LOGGER})()")
        frames = []
        t0 = await ctx.new_page()
        rec(t0, "t0", frames)
        await t0.goto(BASE + "/")
        await hyd(t0)
        await set_theme(t0, "s0")
        await t0.wait_for_timeout(500)
        tabs = []
        for i in range(NTABS):
            p = await ctx.new_page()
            rec(p, f"t{i+1}", frames)
            tabs.append(p)

        async def changer():
            for k in range(1, 6):
                await t0.wait_for_timeout(250)
                await set_theme(t0, f"s{k}")
        await asyncio.gather(changer(), *[p.goto(BASE + "/") for p in tabs])
        await asyncio.gather(*[hyd(p) for p in tabs])
        await t0.wait_for_timeout(4000)
        n_before = len(frames)
        await t0.wait_for_timeout(2000)
        quiet = len(frames) - n_before
        finals = {"t0": await t0.inner_text("#theme")}
        for i, p in enumerate(tabs):
            finals[f"t{i+1}"] = await p.inner_text("#theme")
        se = {"t0": await t0.evaluate("() => window.__se.length")}
        for i, p in enumerate(tabs):
            se[f"t{i+1}"] = await p.evaluate("() => window.__se.length")
        uv = {tag: len(uvi(frames, tag)) for tag in ["t0"] + [f"t{i+1}" for i in range(NTABS)]}
        windows = []
        for _ in range(OBSERVE_S // 5):
            n0 = len(frames)
            await t0.wait_for_timeout(5000)
            windows.append(len(frames) - n0)
        res["S"] = {"observe_windows_5s": windows, "finals": finals, "ls_final": await t0.evaluate("() => localStorage.getItem('be_theme')"),
                    "storage_events_per_tab": se, "uvi_per_tab": uv, "frames_total": len(frames),
                    "frames_in_quiet_2s": quiet, "converged": len(set(finals.values())) == 1}
        print("S:", json.dumps(res["S"]), flush=True)
        await ctx.close()


asyncio.run(main())
