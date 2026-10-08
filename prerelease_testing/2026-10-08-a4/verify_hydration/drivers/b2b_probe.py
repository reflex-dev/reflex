"""Rapid clicks on a sync=True LocalStorage var (src/h4mix, buttons #c0..#c9 set Prefs.syn = "c<i>").

Usage: b2b_probe.py BASE OUT_JSON REPS MODE   MODE: one (1 tab clicks) | two (t1 clicks, t2 open) | alt (t1/t2 alternate, no gap) | warm (t1/t2 alternate 120 ms apart, then t1 clicks back to back)
Per rep (fresh context = fresh profile): wait until quiet, record each tab's final #v-syn, localStorage, the order of t1's
localStorage writes, the syn values each tab SENT (update_vars_internal / click_syn) and RECEIVED (deltas) over the websocket.
"""
import asyncio
import json
import re
import sys
import time

from playwright.async_api import async_playwright

assert "/envs/driver/" in sys.executable, sys.executable
BASE, OUT, REPS, MODE = sys.argv[1].rstrip("/"), sys.argv[2], int(sys.argv[3]), sys.argv[4]
INIT = """(() => { window.__w = []; const o = Storage.prototype.setItem;
  Storage.prototype.setItem = function (k, v) { if (k === 'h4_syn') window.__w.push(String(v)); return o.call(this, k, v); }; })();"""
SYN_IN = re.compile(r'"syn_rx_state_":"([^"]*)"')


def rec(page, tag, log):
    def on_ws(ws):
        if "_event" not in ws.url:
            return
        ws.on("framesent", lambda p: log.append([round(time.time() * 1000) % 100000, tag, "out", _short(p)]))
        ws.on("framereceived", lambda p: log.append([round(time.time() * 1000) % 100000, tag, "in", _short(p)]))
    page.on("websocket", on_ws)


def _short(p):
    if not isinstance(p, str):
        return "<bin>"
    if "click_syn" in p:
        m = re.search(r'"v":"([^"]*)"', p)
        return f"click_syn({m.group(1) if m else '?'})"
    if "update_vars_internal" in p:
        m = re.search(r'syn_rx_state_":("?[^",}]*)', p)
        return f"uvi(syn={m.group(1) if m else '-'})"
    if "hydrate" in p:
        return "hydrate"
    m = SYN_IN.search(p)
    return f"delta(syn={m.group(1)})" if m else ("delta(other)" if p.startswith("42") else p[:20])


async def hyd(p):
    for _ in range(300):
        try:
            if await p.inner_text("#hyd", timeout=200) == "H:yes":
                return True
        except Exception:
            pass
        await p.wait_for_timeout(100)
    return False


async def main():
    out = []
    async with async_playwright() as pw:
        b = await pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        for rep in range(REPS):
            ctx = await b.new_context()
            await ctx.add_init_script(INIT)
            log = []
            t1 = await ctx.new_page()
            rec(t1, "t1", log)
            await t1.goto(BASE + "/")
            await hyd(t1)
            tabs = [t1]
            if MODE in ("two", "alt", "warm"):
                t2 = await ctx.new_page()
                rec(t2, "t2", log)
                await t2.goto(BASE + "/")
                await hyd(t2)
                tabs.append(t2)
            await asyncio.sleep(0.5)
            if MODE == "warm":
                # as in h4_drive C3: the tabs first alternate writes 120 ms apart, then t1 clicks back to back
                for i in range(10):
                    await tabs[i % 2].click(f"#c{i}")
                    await asyncio.sleep(0.12)
                await asyncio.sleep(2.0)
                for t in tabs:
                    await t.evaluate("() => { window.__w = []; }")
            log.clear()
            for i in range(10):
                tab = tabs[i % 2] if MODE == "alt" else t1
                await tab.click(f"#c{i}", delay=0)
            await asyncio.sleep(3.0)
            finals = [await t.inner_text("#v-syn") for t in tabs]
            ls = await t1.evaluate("() => localStorage.getItem('h4_syn')")
            w = [await t.evaluate("() => window.__w") for t in tabs]
            r = {"rep": rep, "finals": finals, "ls": ls, "writes": w, "log": log}
            out.append(r)
            print(f"rep {rep}: finals={finals} ls={ls} t1_writes={w[0]} t2_writes={w[1] if len(w) > 1 else '-'}", flush=True)
            await ctx.close()
        await b.close()
    json.dump(out, open(OUT, "w"), indent=1)


asyncio.run(main())
