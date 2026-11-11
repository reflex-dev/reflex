"""verify_hydration: the 'restore' scenario of vh_tabs.py in a STOCK headful Chromium (no Playwright, none of its
anti-throttling flags), driven over raw CDP. Tabs 1..N-1 are created as real BACKGROUND tabs of one window
(Target.createTarget background=True), so they are hidden and subject to Chrome's background throttling, as restored
tabs of a real browser are. tab0 is the foreground tab where the user clicks.
Needs a display: run under xvfb-run. Debug port 8670 (verify_hydration range).
CLICK_ID "docs": no click; tab i restores /doc/d<i> (its on_load stamps the synced "recently viewed" var) - A3-12.
Usage: vh_rawcdp.py BASE OUT_JSON NTABS STAGGER_MS CLICK_ID CLICK_AFTER_MS [OBSERVE_S=10]
"""
import asyncio
import itertools
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

import websockets

assert f"/envs/{os.environ.get('DRV_VENV', 'driver')}/" in sys.executable, sys.executable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vh_tabs import INIT  # noqa: E402  (same in-page instrumentation as vh_tabs.py)

BASE, OUT, N, STAGGER, CLICK, CLICK_AFTER = sys.argv[1].rstrip("/"), sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5], int(sys.argv[6])
OBS = int(sys.argv[7]) if len(sys.argv) > 7 else 10
PORT = 8670


class CDP:
    def __init__(self, ws):
        self.ws, self.ids, self.pending = ws, itertools.count(1), {}
        self.reader = asyncio.create_task(self._read())

    async def _read(self):
        async for raw in self.ws:
            m = json.loads(raw)
            if "id" in m and m["id"] in self.pending:
                self.pending.pop(m["id"]).set_result(m)

    async def send(self, method, params=None, session=None, timeout=20):
        i = next(self.ids)
        msg = {"id": i, "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = session
        fut = asyncio.get_running_loop().create_future()
        self.pending[i] = fut
        await self.ws.send(json.dumps(msg))
        m = await asyncio.wait_for(fut, timeout)
        if "error" in m:
            raise RuntimeError(f"{method}: {m['error']}")
        return m.get("result", {})

    async def ev(self, session, expr, timeout=20):
        r = await self.send("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True}, session, timeout)
        return r.get("result", {}).get("value")


async def attach(cdp, target_id):
    s = (await cdp.send("Target.attachToTarget", {"targetId": target_id, "flatten": True}))["sessionId"]
    await cdp.send("Page.enable", session=s)
    await cdp.send("Page.addScriptToEvaluateOnNewDocument", {"source": INIT}, s)
    return s


async def hyd(cdp, s, t=40):
    for _ in range(t * 10):
        try:
            if await cdp.ev(s, "document.getElementById('hyd-flag')?.textContent", 2) == "H:yes":
                return round(time.time(), 3)
        except Exception:
            pass
        await asyncio.sleep(0.1)
    return None


async def main():
    udd = tempfile.mkdtemp(prefix="vh_rawcdp_", dir=os.environ.get("VH_TMP"))
    proc = subprocess.Popen(["/opt/pw-browsers/chromium", f"--remote-debugging-port={PORT}", f"--user-data-dir={udd}",
                             "--no-first-run", "--no-default-browser-check", "--no-sandbox", "--disable-gpu",
                             "--window-size=1200,800", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    res = {"args": sys.argv[1:]}
    try:
        op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for _ in range(100):
            try:
                ver = json.load(op.open(f"http://127.0.0.1:{PORT}/json/version", timeout=2))
                break
            except Exception:
                await asyncio.sleep(0.2)
        async with websockets.connect(ver["webSocketDebuggerUrl"], max_size=None) as ws:
            cdp = CDP(ws)
            targets = (await cdp.send("Target.getTargets"))["targetInfos"]
            t0id = next(t["targetId"] for t in targets if t["type"] == "page")
            s0 = await attach(cdp, t0id)
            # returning user: the profile holds theme=green
            await cdp.send("Page.navigate", {"url": BASE + "/"}, s0)
            await hyd(cdp, s0)
            await cdp.ev(s0, "document.getElementById('pick-green').click()")
            await asyncio.sleep(1.0)
            await cdp.send("Page.navigate", {"url": "about:blank"}, s0)
            await asyncio.sleep(0.5)
            sess = [s0]
            for _ in range(N - 1):
                tid = (await cdp.send("Target.createTarget", {"url": "about:blank", "background": True}))["targetId"]
                sess.append(await attach(cdp, tid))
            await cdp.send("Target.activateTarget", {"targetId": t0id})

            async def go(i, s):
                await asyncio.sleep(i * STAGGER / 1000)
                await cdp.send("Page.navigate", {"url": BASE + (f"/doc/d{i}" if CLICK == "docs" else "/")}, s)
            gotos = [asyncio.create_task(go(i, s)) for i, s in enumerate(sess)]
            t0h = await hyd(cdp, s0)
            await asyncio.sleep(max(0, t0h + CLICK_AFTER / 1000 - time.time()))
            res["click_t"] = round(time.time(), 3)
            if CLICK != "docs":
                await cdp.ev(s0, f"document.getElementById('{CLICK}').click()")
            await asyncio.gather(*gotos)
            res["hyd_times"] = [await hyd(cdp, s) for s in sess]
            res["visibility"] = [await cdp.ev(s, "document.visibilityState") for s in sess]
            await asyncio.sleep(3)

            async def total():
                t = 0
                for s in sess:
                    v = await cdp.ev(s, "window.__vh ? window.__vh.sent + window.__vh.recv : 0", 30)
                    t += v or 0
                return t
            wins = []
            for _ in range(max(OBS // 5, 1)):
                n0 = await total()
                await asyncio.sleep(5)
                wins.append(await total() - n0)
            res["windows_5s"] = wins
            res["storm"] = wins[-1] > 50
            res["theme_final"] = [await cdp.ev(s, "document.getElementById('theme')?.textContent", 30) for s in sess]
            res["doc_final"] = [await cdp.ev(s, "document.getElementById('last-doc')?.textContent", 30) for s in sess]
            res["converged"] = len(set(res["doc_final" if CLICK == "docs" else "theme_final"])) == 1
            res["ls_doc"] = await cdp.ev(s0, "localStorage.getItem('vh_last_doc')", 30)
            res["ls_theme"] = await cdp.ev(s0, "localStorage.getItem('vh_theme')", 30)
            res["per_tab"] = [await cdp.ev(s, "JSON.parse(JSON.stringify(window.__vh))", 30) for s in sess]
            res["timer_rate_bg_tab_1s"] = await cdp.ev(sess[-1], "new Promise(r => { let n = 0; const i = setInterval(() => n++, 10); setTimeout(() => { clearInterval(i); r(n); }, 1000); })", 30)
            res["timer_rate_fg_tab_1s"] = await cdp.ev(s0, "new Promise(r => { let n = 0; const i = setInterval(() => n++, 10); setTimeout(() => { clearInterval(i); r(n); }, 1000); })", 30)
            for s in sess:
                try:
                    await cdp.send("Page.navigate", {"url": "about:blank"}, s, 10)
                except Exception:
                    pass
            cdp.reader.cancel()
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except Exception:
            proc.kill()
        shutil.rmtree(udd, ignore_errors=True)
    json.dump(res, open(OUT, "w"), indent=1, default=str)
    print(json.dumps({k: res.get(k) for k in ("click_t", "visibility", "windows_5s", "storm", "converged", "theme_final", "ls_theme", "doc_final", "ls_doc",
                                              "timer_rate_bg_tab_1s", "timer_rate_fg_tab_1s")}))


asyncio.run(main())
