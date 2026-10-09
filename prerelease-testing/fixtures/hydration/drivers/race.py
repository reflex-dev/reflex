"""Cross-tab write races on a sync=True LocalStorage var (app src/h4v, Prefs.syn -> key h4_syn).

Usage: race.py BASE OUT_JSON SERVER_LOG REPS SCEN [SCEN ...]
SCEN:
  gap:<ms>        t1 clicks #c8, <ms> later t2 clicks #c9 (both via in-page el.click(), no Playwright click overhead)
  pwalt           the reporter's b2b alt mode: t1/t2 alternately Playwright-click #c0..#c9, no pause
  onload:<ms>     both tabs on "/", then t1 loads /st/a, <ms> later t2 loads /st/b (on_load stamps syn = st-<slug>)
  bg:<ms>         t1 clicks #bgloop (background task writes bg1..bg5 ~100 ms apart), <ms> later t2 clicks #c9
  freeze:<ms>     t1 starts #bgloop then is FROZEN (CDP Page.setWebLifecycleState) for <ms>; meanwhile, 300 ms after the
                  freeze, t2 clicks #c9; t1 is resumed
Per rep (fresh context = fresh profile): settle 3 s, then record per tab: displayed #v-syn, localStorage, the tab's BACKEND
value (click #probe -> #v-bk), every h4_syn setItem with a shared-clock timestamp, every #v-syn display change, websocket
frames (count in the last 1 s = storm check), the user actions with timestamps, and the server's H4TRACE apply log.
Classification: consistent = every display == localStorage == every backend; last_store = value of the last h4_syn setItem
(any tab); last_server = value of the last handler/background write the SERVER applied (H4TRACE ts); last_action = the
last user action's value. lost = final != last_server.
"""
import asyncio
import json
import os
import sys
import time

from playwright.async_api import async_playwright

assert f"/envs/{os.environ.get('DRV_VENV', 'driver')}/" in sys.executable, sys.executable
BASE, OUT, SLOG, REPS = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3], int(sys.argv[4])
SCENS = sys.argv[5:]
INIT = """(() => {
  const now = () => performance.timeOrigin + performance.now();
  window.__now = now; window.__w = []; window.__disp = []; window.__frames = [];
  const o = Storage.prototype.setItem;
  Storage.prototype.setItem = function (k, v) { if (k === 'h4_syn' && this === localStorage) window.__w.push([now(), String(v)]); return o.call(this, k, v); };
  window.WebSocket = class extends window.WebSocket {
    constructor(...a) { super(...a); this.addEventListener('message', () => window.__frames.push(now())); }
    send(d) { window.__frames.push(now()); return super.send(d); } };
  const watch = () => { const el = document.getElementById('v-syn');
    if (!el) { setTimeout(watch, 20); return; }
    window.__disp.push([now(), el.textContent]);
    new MutationObserver(() => window.__disp.push([now(), el.textContent])).observe(el, {childList: true, characterData: true, subtree: true}); };
  document.addEventListener('DOMContentLoaded', watch);
})();"""
CLICK = "(id) => { const t = window.__now(); document.getElementById(id).click(); return t; }"


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


async def run_rep(b, scen, rep, pos):
    kind, _, arg = scen.partition(":")
    ms = int(arg or 0)
    ctx = await b.new_context()
    await ctx.add_init_script(INIT)
    t1 = await ctx.new_page()
    await t1.goto(BASE + "/")
    await hyd(t1)
    t2 = await ctx.new_page()
    await t2.goto(BASE + "/")
    await hyd(t2)
    tabs = [t1, t2]
    # warm-up write so both tabs and storage hold a known value
    await t1.evaluate(CLICK, "c5")
    await asyncio.sleep(1.2)
    _, pos = read_traces(pos)
    for t in tabs:
        await t.evaluate("() => { window.__w = []; window.__disp = window.__disp.slice(-1); }")
    actions = []
    if kind == "gap":
        actions.append(["t1", await t1.evaluate(CLICK, "c8"), "c8"])
        if ms:
            await asyncio.sleep(ms / 1000)
        actions.append(["t2", await t2.evaluate(CLICK, "c9"), "c9"])
    elif kind == "pwalt":
        for i in range(10):
            tab = tabs[i % 2]
            ts = await tab.evaluate("() => window.__now()")
            await tab.click(f"#c{i}", delay=0)
            actions.append([f"t{i % 2 + 1}", ts, f"c{i}"])
    elif kind == "onload":
        actions.append(["t1", await t1.evaluate("() => window.__now()"), "st-a"])
        await t1.goto(BASE + "/st/a", wait_until="commit")
        if ms:
            await asyncio.sleep(ms / 1000)
        actions.append(["t2", await t2.evaluate("() => window.__now()"), "st-b"])
        await t2.goto(BASE + "/st/b", wait_until="commit")
        await hyd(t1)
        await hyd(t2)
    elif kind == "bg":
        actions.append(["t1", await t1.evaluate(CLICK, "bgloop"), "bgloop"])
        await asyncio.sleep(ms / 1000)
        actions.append(["t2", await t2.evaluate(CLICK, "c9"), "c9"])
    elif kind == "freeze":
        cdp = await ctx.new_cdp_session(t1)
        actions.append(["t1", await t1.evaluate(CLICK, "bgloop"), "bgloop"])
        await asyncio.sleep(0.05)
        await cdp.send("Page.setWebLifecycleState", {"state": "frozen"})
        await asyncio.sleep(0.3)
        actions.append(["t2", await t2.evaluate(CLICK, "c9"), "c9"])
        await asyncio.sleep(max(0, ms / 1000 - 0.3))
        await cdp.send("Page.setWebLifecycleState", {"state": "active"})
        actions.append(["t1", await t1.evaluate("() => window.__now()"), "resume"])
    await asyncio.sleep(3.0)
    nowv = await t1.evaluate("() => window.__now()")
    quiet = [await t.evaluate("(n) => window.__frames.filter((x) => x > n - 1000).length", nowv) for t in tabs]
    finals = [await t.inner_text("#v-syn") for t in tabs]
    ls = await t1.evaluate("() => localStorage.getItem('h4_syn')")
    for t in tabs:
        await t.evaluate("() => document.getElementById('probe').click()")
    await asyncio.sleep(0.6)
    bks = [(await t.inner_text("#v-bk")).split("|")[0] for t in tabs]
    writes = sorted([[w[0], f"t{i + 1}", w[1]] for i, t in enumerate(tabs) for w in await t.evaluate("() => window.__w")])
    disp = [await t.evaluate("() => window.__disp") for t in tabs]
    traces, pos = read_traces(pos)
    traces = [t for t in traces if t["tag"] in ("CLICK", "BGLOOP", "STAMP")]
    await ctx.close()
    vals = set(finals) | {ls} | set(bks)
    last_store = writes[-1][2] if writes else None
    last_server = max(traces, key=lambda t: t["ts"])["v"] if traces else None
    last_action = max((a for a in actions if a[2] not in ("bgloop", "resume")), key=lambda a: a[1])[2]
    # a tab "flipped" if after showing its own last written value it ends on another one
    flips = []
    for i, d in enumerate(disp):
        own = [a[2] for a in actions if a[0] == f"t{i + 1}" and a[2].startswith("c")]
        shown = [x[1] for x in d]
        if own and own[-1] in shown and finals[i] != own[-1]:
            flips.append(f"t{i + 1}:{own[-1]}->{finals[i]}")
    r = {
        "scen": scen, "rep": rep, "finals": finals, "ls": ls, "backend": bks, "consistent": len(vals) == 1,
        "last_store": last_store, "last_server": last_server, "last_action": last_action,
        "lost": (len(vals) == 1 and last_server is not None and finals[0] != last_server),
        "quiet_frames_1s": quiet, "nwrites": [sum(1 for w in writes if w[1] == "t1"), sum(1 for w in writes if w[1] == "t2")],
        "flips": flips, "actions": actions, "writes": writes, "traces": traces, "disp": disp,
    }
    t0 = actions[0][1]
    srv = " ".join(f"{t['tag'][0]}:{t['v']}@{t['ts'] - t0:+.0f}" for t in traces)
    st = " ".join(f"{w[1]}:{w[2]}@{w[0] - t0:+.0f}" for w in writes[-6:])
    print(f"{scen} rep{rep}: finals={finals} ls={ls} backend={bks} consistent={r['consistent']} last_action={last_action} "
          f"last_server={last_server} last_store={last_store} lost={r['lost']} flips={flips} quiet={quiet} nwrites={r['nwrites']}\n"
          f"    server: {srv}\n    stores(last6): {st}", flush=True)
    return r, pos


async def main():
    out = []
    pos = os.path.getsize(SLOG)
    async with async_playwright() as pw:
        b = await pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        for scen in SCENS:
            for rep in range(REPS):
                r, pos = await run_rep(b, scen, rep, pos)
                out.append(r)
        await b.close()
    json.dump(out, open(OUT, "w"), indent=1)
    print("SUMMARY")
    for scen in SCENS:
        rs = [r for r in out if r["scen"] == scen]
        fin = {}
        for r in rs:
            k = r["finals"][0] if r["consistent"] else "INCONSISTENT"
            fin[k] = fin.get(k, 0) + 1
        print(f"  {scen:12} n={len(rs)} finals={fin} consistent={sum(r['consistent'] for r in rs)}/{len(rs)} "
              f"=last_action={sum(r['consistent'] and r['finals'][0] == r['last_action'] for r in rs)} "
              f"=last_store={sum(r['consistent'] and r['finals'][0] == r['last_store'] for r in rs)} "
              f"=last_server={sum(r['consistent'] and r['finals'][0] == r['last_server'] for r in rs)} "
              f"flips={sum(bool(r['flips']) for r in rs)} storm(quiet>10)={sum(max(r['quiet_frames_1s']) > 10 for r in rs)} "
              f"writes/rep max={max(sum(r['nwrites']) for r in rs)}")


asyncio.run(main())
