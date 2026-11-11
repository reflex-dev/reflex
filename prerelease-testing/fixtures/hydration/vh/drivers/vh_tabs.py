"""verify_hydration multi-tab driver for sync=True LocalStorage (src/vhsync), written independently of the explorer's drivers.

All tabs share ONE profile (as tabs of one real browser window do). Websocket traffic, storage events and the #theme
timeline are counted IN THE PAGE (init script wrapping window.WebSocket) so a storm cannot crash Playwright's node driver.

Scenarios:
  restore  browser (re)start: all N tabs (tab0 included) start loading "/" at once; the user acts in tab0 as soon as
           tab0 shows H:yes (clicks per --clicks, offsets in ms after that moment).
  reload   N tabs loaded, hydrated and quiet; tabs 1..N-1 reload at once; the user acts in tab0 (offsets after the reload).
  docs     N tabs restored on /doc/d0../doc/d<N-1> at once (each on_load stamps a different "recently viewed" value).
  docs-restart  N tabs on /doc/d0../doc/d<N-1>, loaded ONE AT A TIME (quiet), then --restart-cmd runs (e.g. touch the app
           module so the dev backend reloads, as on every save or a deploy): every tab reconnects and re-runs its on_load.
  open     tab0 loaded and quiet; the user clicks in tab0 (offsets after t_ref) while N-1 NEW tabs start loading at once,
           --late-ms after t_ref (default 0). The explorer's Part S shape; ntabs=2 = one late-booting tab.
Options:
  --headful      run headful (needs DISPLAY; use xvfb-run): only the front tab is visible, the others are background tabs.
  --throttle     drop Playwright's default --disable-background-timer-throttling / --disable-renderer-backgrounding /
                 --disable-backgrounding-occluded-windows so background tabs are throttled like in a stock Chrome.
  --persistent   launch_persistent_context (a real on-disk profile) instead of browser.new_context().
  --clicks       comma list of <button-id>@<ms>, e.g. "toggle@0,toggle@700" or "pick-red@300".
  --observe S    observation after settle: frames per 5 s window (default 15 s).
  --heal         after the observation, click pick-blue in tab0 once and observe 10 s more (does it converge?).
Usage: vh_tabs.py BASE OUT_JSON SCENARIO NTABS [options]
"""
import argparse
import asyncio
import json
import os
import shutil
import sys
import tempfile
import time

from playwright.async_api import async_playwright

assert f"/envs/{os.environ.get('DRV_VENV', 'driver')}/" in sys.executable, sys.executable
CHROMIUM = "/opt/pw-browsers/chromium"

INIT = r"""(() => {
  window.__vh = {sent: 0, recv: 0, uvi: 0, se: 0, se_vals: [], tl: [], opened: 0, log: []};
  const T = () => Math.round(performance.timeOrigin + performance.now());
  const L = (d, m) => { if (window.__vh.log.length < 40) window.__vh.log.push([T(), d, typeof m === 'string' ? m.slice(0, 600) : '<bin>']); };
  const WS = window.WebSocket;
  const Wrapped = function(...a) {
    const ws = new WS(...a);
    if (String(a[0]).includes('_event')) {
      window.__vh.opened++;
      const s = ws.send.bind(ws);
      ws.send = (d) => { window.__vh.sent++; L('out', d);
        if (typeof d === 'string' && d.includes('update_vars_internal')) window.__vh.uvi++; return s(d); };
      ws.addEventListener('message', (e) => { window.__vh.recv++; L('in', e.data); });
    }
    return ws;
  };
  Wrapped.prototype = WS.prototype; Object.assign(Wrapped, WS);
  window.WebSocket = Wrapped;
  window.addEventListener('storage', e => { window.__vh.se++; L('storage', e.key + ':' + e.oldValue + '->' + e.newValue);
    if (window.__vh.se_vals.length < 60) window.__vh.se_vals.push([Math.round(performance.now()), e.key, e.oldValue, e.newValue]); });
  let last = null;
  setInterval(() => { const el = document.getElementById('theme'); const v = el ? el.textContent : null;
    if (v !== last && window.__vh.tl.length < 300) { window.__vh.tl.push([Math.round(performance.timeOrigin + performance.now()), v]); last = v; } }, 25);
})();"""


def parse():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("out")
    ap.add_argument("scenario", choices=["restore", "reload", "docs", "open", "docs-restart"])
    ap.add_argument("ntabs", type=int)
    ap.add_argument("--headful", action="store_true")
    ap.add_argument("--throttle", action="store_true")
    ap.add_argument("--persistent", action="store_true")
    ap.add_argument("--clicks", default="")
    ap.add_argument("--observe", type=int, default=15)
    ap.add_argument("--heal", action="store_true")
    ap.add_argument("--late-ms", type=int, default=0)
    ap.add_argument("--path", default="/")
    ap.add_argument("--restart-cmd", default="")
    ap.add_argument("--restart-wait", type=int, default=12)
    ap.add_argument("--stagger", type=int, default=0, help="restore/docs: tab i starts loading i*STAGGER ms after tab0")
    return ap.parse_args()


async def hyd(page, t=40):
    for _ in range(t * 10):
        try:
            if await page.inner_text("#hyd-flag", timeout=300) == "H:yes":
                return round(time.time(), 3)
        except Exception:
            pass
        await asyncio.sleep(0.1)
    return None


async def vh(page):
    try:
        return await page.evaluate("() => window.__vh")
    except Exception as e:
        return {"error": str(e)[:200]}


async def total(pages):
    t = 0
    for p in pages:
        c = await vh(p)
        t += c.get("sent", 0) + c.get("recv", 0)
    return t


async def do_clicks(page, spec, t_ref):
    """Click buttons at offsets (ms) after t_ref (wall clock). Returns the actual click times."""
    done = []
    for item in [s for s in spec.split(",") if s]:
        bid, _, ms = item.partition("@")
        wait = t_ref + int(ms or 0) / 1000 - time.time()
        if wait > 0:
            await asyncio.sleep(wait)
        t = time.time()
        try:
            await page.click(f"#{bid}", timeout=8000)
            done.append((bid, round(t, 3), round(time.time() - t, 3)))
        except Exception as e:  # a storm can make the page too busy to take a click
            done.append((bid, round(t, 3), f"CLICK FAILED {type(e).__name__}"))
    return done


async def observe(pages, seconds):
    wins = []
    for _ in range(max(seconds // 5, 1)):
        n0 = await total(pages)
        await asyncio.sleep(5)
        wins.append(await total(pages) - n0)
    return wins


async def snapshot(pages, key):
    out = []
    for p in pages:
        try:
            out.append(await p.inner_text(f"#{key}", timeout=2000))
        except Exception as e:
            out.append(f"ERR {str(e)[:60]}")
    return out


async def main():
    a = parse()
    res = {"args": vars(a), "scenario": a.scenario, "t_start": round(time.time(), 3)}
    ignore = ["--disable-background-timer-throttling", "--disable-renderer-backgrounding",
              "--disable-backgrounding-occluded-windows"] if a.throttle else []
    udd = tempfile.mkdtemp(prefix="vh_profile_", dir=os.environ.get("VH_TMP"))
    async with async_playwright() as pw:
        kw = dict(executable_path=CHROMIUM, headless=not a.headful, ignore_default_args=ignore)
        if a.persistent:
            ctx = await pw.chromium.launch_persistent_context(udd, **kw)
            browser = None
        else:
            browser = await pw.chromium.launch(**kw)
            ctx = await browser.new_context()
        await ctx.add_init_script(INIT)
        try:
            await run(a, ctx, res)
        finally:
            await ctx.close()
            if browser:
                await browser.close()
    shutil.rmtree(udd, ignore_errors=True)
    json.dump(res, open(a.out, "w"), indent=1, default=str)
    keys = ("scenario", "clicks", "ok_hyd", "windows_5s", "storm", "converged", "theme_final", "ls_theme", "doc_final",
            "ls_doc", "tab0_timeline", "heal_windows_5s", "heal_converged", "visibility")
    print(json.dumps({k: res.get(k) for k in keys}, default=str))


async def run(a, ctx, res):
    base = a.base.rstrip("/")
    # A returning user: the profile already holds a value for both synced keys.
    w = ctx.pages[0] if ctx.pages else await ctx.new_page()
    await w.goto(base + "/")
    await hyd(w)
    await w.click("#pick-green")
    await asyncio.sleep(0.8)
    await w.goto(base + "/doc/warm")
    await hyd(w)
    await asyncio.sleep(0.5)
    await w.goto("about:blank")
    clicks = []
    if a.scenario in ("restore", "docs"):
        pages = [w] + [await ctx.new_page() for _ in range(a.ntabs - 1)]
        urls = [base + (f"/doc/d{i}" if a.scenario == "docs" else a.path) for i in range(a.ntabs)]
        await pages[0].bring_to_front()
        async def go(i, p, u):
            await asyncio.sleep(i * a.stagger / 1000)
            await p.goto(u)
        gotos = [asyncio.create_task(go(i, p, u)) for i, (p, u) in enumerate(zip(pages, urls))]
        t0h = await hyd(pages[0])
        if a.clicks:
            clicks = await do_clicks(pages[0], a.clicks, t0h)
        await asyncio.gather(*gotos, return_exceptions=True)
    elif a.scenario == "docs-restart":
        pages = [w] + [await ctx.new_page() for _ in range(a.ntabs - 1)]
        for i, p in enumerate(pages):
            await p.goto(base + f"/doc/d{i}")
            await hyd(p)
            await asyncio.sleep(0.5)
        await asyncio.sleep(2)
        res["before_restart_windows_5s"] = await observe(pages, 5)
        res["before_restart_docs"] = await snapshot(pages, "last-doc")
        res["restart_t"] = round(time.time(), 3)
        res["restart_rc"] = (await (await asyncio.create_subprocess_shell(a.restart_cmd)).wait()) if a.restart_cmd else None
        await asyncio.sleep(a.restart_wait)
        res["opened_after_restart"] = [(await vh(p)).get("opened") for p in pages]
    elif a.scenario == "reload":
        pages = [w] + [await ctx.new_page() for _ in range(a.ntabs - 1)]
        for p in pages:
            await p.goto(base + a.path)
        await asyncio.gather(*[hyd(p) for p in pages])
        await pages[0].bring_to_front()
        await asyncio.sleep(2)
        t_rel = time.time()
        rel = [asyncio.create_task(p.reload()) for p in pages[1:]]
        clicks = await do_clicks(pages[0], a.clicks, t_rel)
        await asyncio.gather(*rel, return_exceptions=True)
    else:  # open: tab0 loaded and quiet; ntabs-1 NEW tabs open at once, --late-ms after the user's first action time
        pages = [w]
        await w.goto(base + a.path)
        await hyd(w)
        await asyncio.sleep(2)
        new = [await ctx.new_page() for _ in range(a.ntabs - 1)]
        await pages[0].bring_to_front()
        t_c = time.time()
        task = asyncio.create_task(do_clicks(pages[0], a.clicks, t_c))
        await asyncio.sleep(a.late_ms / 1000)
        gotos = [asyncio.create_task(p.goto(base + a.path)) for p in new]
        clicks = await task
        await asyncio.gather(*gotos, return_exceptions=True)
        pages += new
        await pages[0].bring_to_front()
    res["clicks"] = clicks
    res["hyd_times"] = await asyncio.gather(*[hyd(p) for p in pages])
    res["ok_hyd"] = all(res["hyd_times"])
    await asyncio.sleep(3)
    res["windows_5s"] = await observe(pages, a.observe)
    res["storm"] = res["windows_5s"][-1] > 50
    res["theme_final"] = await snapshot(pages, "theme")
    res["doc_final"] = await snapshot(pages, "last-doc")
    key = "doc_final" if a.scenario.startswith("docs") else "theme_final"
    res["converged"] = len(set(res[key])) == 1
    res["ls_theme"] = await pages[0].evaluate("() => localStorage.getItem('vh_theme')")
    res["ls_doc"] = await pages[0].evaluate("() => localStorage.getItem('vh_last_doc')")
    res["visibility"] = [await p.evaluate("() => document.visibilityState") for p in pages]
    res["per_tab"] = [await vh(p) for p in pages]
    res["tab0_timeline"] = [v for _, v in res["per_tab"][0].get("tl", [])][:40]
    if a.heal:
        await pages[0].bring_to_front()
        await pages[0].click("#pick-blue", timeout=5000)
        res["heal_click"] = round(time.time(), 3)
        await asyncio.sleep(3)
        res["heal_windows_5s"] = await observe(pages, 10)
        res["heal_final"] = await snapshot(pages, "theme")
        res["heal_converged"] = len(set(res["heal_final"])) == 1 and res["heal_windows_5s"][-1] <= 50
    for p in pages:
        try:
            await p.goto("about:blank", timeout=5000)
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
