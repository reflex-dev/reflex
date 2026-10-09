"""O-2 window: another tab stores a newer value while a returning tab boots (app src/h4v, Prefs.syn -> key h4_syn).

Usage: bootwin.py BASE OUT_JSON SERVER_LOG PATH OFFSET_MS [OFFSET_MS ...]
Per offset (fresh context): t2 opens "/" and clicks #c5 (V0 = c5 stored); t1 opens PATH (returning tab) and settles; t2 is
armed: when t1's NEXT boot sends its hydrate event (BroadcastChannel from t1's websocket send hook) t2 clicks #c9 (V1, the
user's newer value) OFFSET_MS later; t1 reloads PATH. PATH "/" has no on_load; "/norm" has an on_load that re-assigns
syn (a second boot delta carrying the boot value V0); "/normslow" does the same after 300 ms.
Records t1's incoming frames that carry syn (relative to t1's hydrate send), every h4_syn setItem in both tabs, t2's
display sequence, finals, localStorage, each tab's backend value (#probe), frames in the last second (storm check).
lost = everything converged on something other than c9; reverted = t2 showed c9 and later something else.
"""
import asyncio
import json
import os
import re
import sys

from playwright.async_api import async_playwright

assert f"/envs/{os.environ.get('DRV_VENV', 'driver')}/" in sys.executable, sys.executable
BASE, OUT, SLOG, PATH = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3], sys.argv[4]
OFFS = [int(x) for x in sys.argv[5:]]
INIT = """(() => {
  const now = () => performance.timeOrigin + performance.now();
  window.__now = now; window.__w = []; window.__disp = []; window.__frames = []; window.__in = []; window.__hyd = null;
  const o = Storage.prototype.setItem;
  Storage.prototype.setItem = function (k, v) { if (k === 'h4_syn' && this === localStorage) window.__w.push([now(), String(v)]); return o.call(this, k, v); };
  window.WebSocket = class extends window.WebSocket {
    constructor(...a) { super(...a); this.addEventListener('message', (e) => { const t = now(); window.__frames.push(t);
      if (typeof e.data === 'string' && e.data.includes('syn_rx_state_')) {
        const m = e.data.match(/"syn_rx_state_":"([^"]*)"/); const h = e.data.match(/"is_hydrated_rx_state_":(true|false)/);
        window.__in.push([t, m ? m[1] : '?', h ? h[1] : '-']); } }); }
    send(d) { const t = now(); window.__frames.push(t);
      if (window.__hyd === null && typeof d === 'string' && d.includes('hydrate')) { window.__hyd = t;
        new BroadcastChannel('bootwin').postMessage(t); }
      return super.send(d); } };
  const watch = () => { const el = document.getElementById('v-syn');
    if (!el) { setTimeout(watch, 20); return; }
    window.__disp.push([now(), el.textContent]);
    new MutationObserver(() => window.__disp.push([now(), el.textContent])).observe(el, {childList: true, characterData: true, subtree: true}); };
  document.addEventListener('DOMContentLoaded', watch);
})();"""
ARM = """(off) => { window.__fired = null; const bc = new BroadcastChannel('bootwin');
  bc.onmessage = () => { bc.onmessage = null; setTimeout(() => { window.__fired = window.__now(); document.getElementById('c9').click(); }, off); }; }"""


async def hyd(p, timeout_s=30):
    for _ in range(timeout_s * 10):
        try:
            if await p.inner_text("#hyd", timeout=200) == "H:yes":
                return True
        except Exception:
            pass
        await p.wait_for_timeout(100)
    return False


def read_traces(pos):
    with open(SLOG, "rb") as f:
        f.seek(pos)
        data = f.read()
    tr = []
    for line in data.decode("utf-8", "replace").splitlines():
        if "H4TRACE" in line:
            tag, _, js = line.split("H4TRACE ", 1)[1].partition(" ")
            try:
                tr.append({"tag": tag, **json.loads(js)})
            except Exception:
                pass
    return tr, pos + len(data)


async def main():
    out = []
    pos = os.path.getsize(SLOG)
    async with async_playwright() as pw:
        b = await pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        for off in OFFS:
            ctx = await b.new_context()
            await ctx.add_init_script(INIT)
            t2 = await ctx.new_page()
            await t2.goto(BASE + "/")
            await hyd(t2)
            await t2.click("#c5")
            await asyncio.sleep(0.8)
            t1 = await ctx.new_page()
            await t1.goto(BASE + PATH)
            await hyd(t1)
            await asyncio.sleep(1.0)
            await t2.evaluate("() => { window.__w = []; window.__disp = window.__disp.slice(-1); }")
            await t2.evaluate(ARM, off)
            _, pos = read_traces(pos)
            await t1.reload(wait_until="commit")
            await hyd(t1)
            await asyncio.sleep(2.5)
            nowv = await t1.evaluate("() => window.__now()")
            quiet = [await t.evaluate("(n) => window.__frames.filter((x) => x > n - 1000).length", nowv) for t in (t1, t2)]
            finals = [await t.inner_text("#v-syn") for t in (t1, t2)]
            ls = await t1.evaluate("() => localStorage.getItem('h4_syn')")
            for t in (t1, t2):
                await t.evaluate("() => document.getElementById('probe').click()")
            await asyncio.sleep(0.6)
            bks = [(await t.inner_text("#v-bk")).split("|")[0] for t in (t1, t2)]
            h = await t1.evaluate("() => window.__hyd")
            fired = await t2.evaluate("() => window.__fired")
            t1in = [[round(x[0] - h, 1), x[1], x[2]] for x in await t1.evaluate("() => window.__in")]
            writes = sorted([[round(w[0] - h, 1), tag, w[1]] for tag, t in (("t1", t1), ("t2", t2)) for w in await t.evaluate("() => window.__w")])
            d2 = [[round(x[0] - h, 1), x[1]] for x in await t2.evaluate("() => window.__disp")]
            traces, pos = read_traces(pos)
            await ctx.close()
            seen9 = [i for i, x in enumerate(d2) if x[1] == "c9"]
            reverted = bool(seen9) and any(x[1] != "c9" for x in d2[seen9[0]:])
            vals = set(finals) | {ls} | set(bks)
            r = {"path": PATH, "offset": off, "click_at": round(fired - h, 1) if fired else None, "finals": finals, "ls": ls,
                 "backend": bks, "consistent": len(vals) == 1, "lost": len(vals) == 1 and finals[0] != "c9",
                 "reverted": reverted, "quiet_frames_1s": quiet, "t1_in": t1in, "writes": writes, "t2_disp": d2,
                 "traces": [{k: (round(v - h, 1) if k == "ts" else v) for k, v in t.items()} for t in traces]}
            out.append(r)
            print(f"{PATH} off={off} click@{r['click_at']} finals={finals} ls={ls} backend={bks} consistent={r['consistent']} "
                  f"lost={r['lost']} reverted={reverted} quiet={quiet}\n    t1_in={t1in}\n    writes={writes}\n    t2_disp={d2[-6:]}\n"
                  f"    server={[(t['tag'], t['v'], t['ts']) for t in r['traces']]}", flush=True)
        await b.close()
    json.dump(out, open(OUT, "w"), indent=1)
    n = len(out)
    print(f"SUMMARY {PATH}: n={n} consistent={sum(r['consistent'] for r in out)} lost={sum(r['lost'] for r in out)} "
          f"reverted(transient or final)={sum(r['reverted'] for r in out)} storm={sum(max(r['quiet_frames_1s']) > 10 for r in out)} "
          f"finals={sorted(set(r['finals'][0] if r['consistent'] else 'INCONSISTENT' for r in out))}")


asyncio.run(main())
