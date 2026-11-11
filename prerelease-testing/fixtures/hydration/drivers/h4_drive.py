"""a4_hydration Part 2 driver for src/h4mix (reflex#7505 regression hunt).

Usage: h4_drive.py BASE OUT_JSON [only=C1,C2,...]
Every check uses a fresh browser context (= a fresh profile) unless it says otherwise. Per context it records
console errors/warnings, failed requests / 4xx-5xx, websocket frame counts per page and every
localStorage/sessionStorage setItem call the page makes (wrapped Storage.prototype.setItem, from an init script).
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
ONLY = set(sys.argv[3].split(",")) if len(sys.argv) > 3 and sys.argv[3] else None

UNI = "ünïcödé ✓ 日本語 🎉 \"q\" 'a' \\ end"
JSONISH = '{"a": [1, 2, {"b": null}], "c": "x\\"y", "d": true}'
LONG = "L" + "0123456789abcdef" * 400 + "Z"

INIT = """(() => {
  window.__w = []; window.__se = []; window.__frames = {in: 0, out: 0};
  const orig = Storage.prototype.setItem;
  Storage.prototype.setItem = function (k, v) {
    window.__w.push([Math.round(performance.now()), this === window.localStorage ? 'L' : 'S', k, String(v).slice(0, 80)]);
    return orig.call(this, k, v);
  };
  window.addEventListener('storage', e => window.__se.push([Math.round(performance.now()), e.key, (e.oldValue || '').slice(0, 40), (e.newValue || '').slice(0, 40)]));
  const WS = window.WebSocket;
  window.WebSocket = function (...a) {
    const ws = new WS(...a);
    if (String(a[0]).includes('_event')) {
      ws.addEventListener('message', () => { window.__frames.in++; });
      const send = ws.send.bind(ws);
      ws.send = (d) => { window.__frames.out++; return send(d); };
    }
    return ws;
  };
  window.WebSocket.prototype = WS.prototype;
  Object.assign(window.WebSocket, {CONNECTING: 0, OPEN: 1, CLOSING: 2, CLOSED: 3});
})();"""

IDS = ["v-syn", "v-nos", "v-ses", "v-ck", "v-san", "v-sanns", "v-sub", "v-subck", "v-last", "v-visits", "v-bgruns", "v-shns", "v-shs",
       "box-a-syn", "box-a-nos", "box-b-syn", "box-b-nos"]
RESULTS = {"base": BASE, "checks": {}, "noise": {}}


class Ctx:
    def __init__(self, browser, label):
        self.browser, self.label = browser, label
        self.console, self.failed, self.pages = [], [], []

    async def __aenter__(self):
        self.ctx = await self.browser.new_context()
        await self.ctx.add_init_script(INIT)
        await self.ctx.route(BASE + "/__seed", lambda r: r.fulfill(body="<html><body>seed</body></html>", content_type="text/html"))
        return self

    async def __aexit__(self, *a):
        RESULTS["noise"][self.label] = {"console": self.console[:40], "failed": self.failed[:40]}
        await self.ctx.close()

    async def page(self, path="/", wait=True, tag=None):
        p = await self.ctx.new_page()
        tag = tag or f"p{len(self.pages)}"
        p.on("console", lambda m: self.console.append([tag, m.type, m.text[:300]]) if m.type in ("error", "warning") else None)
        p.on("pageerror", lambda e: self.console.append([tag, "pageerror", str(e)[:300]]))
        p.on("requestfailed", lambda r: self.failed.append([tag, r.url[-80:], r.failure]))
        p.on("response", lambda r: self.failed.append([tag, r.url[-80:], r.status]) if r.status >= 400 else None)
        self.pages.append(p)
        if path is not None:
            await p.goto(BASE + path)
            if wait:
                assert await hyd(p), f"{tag} {path} not hydrated"
        return p

    async def seed(self, items: dict, remove=()):
        """Write localStorage directly from a non-app page of the same origin (another tab / devtools / other app version)."""
        p = await self.ctx.new_page()
        await p.goto(BASE + "/__seed")
        await p.evaluate("([items, rm]) => { for (const [k, v] of Object.entries(items)) localStorage.setItem(k, v); for (const k of rm) localStorage.removeItem(k); }", [items, list(remove)])
        await p.close()

    async def cookies(self):
        return {c["name"]: {"value": c["value"], "expires": round(c["expires"])} for c in await self.ctx.cookies() if c["name"].startswith("h4_") or "box" in c["name"].lower()}


async def hyd(p, t=40):
    for _ in range(t * 10):
        try:
            if await p.inner_text("#hyd", timeout=200) == "H:yes":
                return True
        except Exception:
            pass
        await p.wait_for_timeout(100)
    return False


async def vals(p):
    return await p.evaluate("(ids) => Object.fromEntries(ids.map(i => [i, document.getElementById(i)?.textContent ?? null]))", IDS)


async def ls(p):
    return await p.evaluate("() => Object.fromEntries(Object.entries(localStorage).filter(([k]) => !['theme','last_compiled_theme'].includes(k)))")


async def ss(p):
    return await p.evaluate("() => Object.fromEntries(Object.entries(sessionStorage).filter(([k]) => k !== 'token'))")


async def writes(p, reset=False):
    w = await p.evaluate("(r) => { const w = window.__w; if (r) window.__w = []; return w; }", reset)
    return w


async def frames(p):
    return await p.evaluate("() => ({...window.__frames})")


async def set_in(p, field, value):
    await p.fill(f"#in-{field}", value)
    await p.locator(f"#in-{field}").blur()


async def wait_until(fn, timeout=6.0, step=0.1):
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        last = await fn()
        if last[0]:
            return True, round(time.time() - t0, 2), last[1]
        await asyncio.sleep(step)
    return False, round(time.time() - t0, 2), last[1] if last else None


async def quiet(pages, secs=2.0):
    before = [await frames(p) for p in pages]
    await asyncio.sleep(secs)
    after = [await frames(p) for p in pages]
    return sum(a["in"] + a["out"] - b["in"] - b["out"] for a, b in zip(after, before))


def record(name, ok, **info):
    RESULTS["checks"][name] = {"ok": ok, **info}
    print(f"{'PASS' if ok else 'FAIL'} {name} {json.dumps(info, ensure_ascii=False)[:600]}", flush=True)


def want(name):
    return ONLY is None or name.split("_")[0] in ONLY or name in ONLY


async def c1_fresh(b):
    """F-002/F-003: a fresh profile gets no storage keys written on / and /other; /stamp's on_load writes only its own."""
    async with Ctx(b, "C1") as c:
        p = await c.page("/")
        await asyncio.sleep(1.5)
        r_root = {"ls": await ls(p), "ss": await ss(p), "ck": await c.cookies(), "writes": await writes(p)}
        await p.click("#nav-other")
        await asyncio.sleep(1.5)
        r_other = {"ls": await ls(p), "ss": await ss(p), "ck": await c.cookies()}
        p2 = await c.page("/other")
        await asyncio.sleep(1.0)
        r_other2 = {"ls": await ls(p2), "ck": await c.cookies(), "writes": await writes(p2)}
        ok = not r_root["ls"] and not r_root["ss"] and not r_root["ck"] and not r_other["ls"] and not r_other2["ls"] and not r_other2["ck"]
        record("C1_fresh_no_writes", ok, root=r_root, other_nav=r_other, other_new_tab=r_other2)
        p3 = await c.page("/stamp")
        await asyncio.sleep(1.0)
        l3 = await ls(p3)
        record("C1_fresh_stamp_onload_only", set(l3) == {"h4_last", "h4_visits"} and l3.get("h4_last") == "stamp@/stamp", ls=l3, ck=await c.cookies())


async def c2_nosync(b):
    """sync=False LocalStorage: handler writes persist, including when the value equals the one sent at boot and when another tab wrote the key meanwhile."""
    async with Ctx(b, "C2") as c:
        t1 = await c.page("/", tag="t1")
        await set_in(t1, "nos", "A")
        ok1 = await wait_until(lambda: _lsget(t1, "h4_nos", "A"))
        await t1.reload()
        await hyd(t1)
        v = await vals(t1)
        record("C2_nos_persist_reload", ok1[0] and v["v-nos"] == "A", ls_wait=ok1, shown=v["v-nos"])
        # tab1 boots with h4_nos=A (sent at boot); tab2 writes B; tab1 must NOT follow; tab1 then sets A again -> must be stored.
        await t1.close()
        t1 = await c.page("/", tag="t1b")
        t2 = await c.page("/", tag="t2")
        await set_in(t2, "nos", "B")
        okb = await wait_until(lambda: _lsget(t2, "h4_nos", "B"))
        await asyncio.sleep(1.0)
        t1v = (await vals(t1))["v-nos"]
        record("C2_nos_not_followed", okb[0] and t1v == "A", ls_wait=okb, tab1_shows=t1v)
        await writes(t1, reset=True)
        await set_in(t1, "nos", "A")
        oka = await wait_until(lambda: _lsget(t1, "h4_nos", "A"))
        w = [x for x in await writes(t1) if x[2] == "h4_nos"]
        await t1.reload()
        await hyd(t1)
        shown = (await vals(t1))["v-nos"]
        record("C2_nos_write_equal_to_boot_value_after_other_tab", oka[0] and shown == "A", ls_wait=oka, tab1_writes=w, reload_shows=shown)
        # same value via a handler that assigns every var to itself, after another tab changed the key
        await set_in(t2, "nos", "C")
        await wait_until(lambda: _lsget(t2, "h4_nos", "C"))
        await writes(t1, reset=True)
        await t1.click("#same")
        oks = await wait_until(lambda: _lsget(t1, "h4_nos", "A"), timeout=3)
        w = await writes(t1)
        record("C2_same_value_handler_rewrites_nos", oks[0], ls_wait=oks, ls=await ls(t1), tab1_writes=w)


async def _lsget(p, k, want_v):
    v = await p.evaluate("(k) => localStorage.getItem(k)", k)
    return v == want_v, v


async def _all(pages, ident, want_v):
    vs = [(await vals(p))[ident] for p in pages]
    return all(v == want_v for v in vs), vs


async def c3_sync(b):
    """sync=True: follows across tabs; a handler setting the value this tab sent at boot after another tab changed it is stored and followed."""
    async with Ctx(b, "C3") as c:
        await c.seed({"h4_syn": "A"})
        t1 = await c.page("/", tag="t1")
        t2 = await c.page("/", tag="t2")
        await set_in(t2, "syn", "B")
        okb = await wait_until(lambda: _all([t1, t2], "v-syn", "B"))
        record("C3_syn_follows", okb[0], wait=okb, ls=(await ls(t1)).get("h4_syn"))
        await writes(t1, reset=True)
        await set_in(t1, "syn", "A")
        oka = await wait_until(lambda: _all([t1, t2], "v-syn", "A"))
        l = (await ls(t1)).get("h4_syn")
        q = await quiet([t1, t2])
        record("C3_syn_write_equal_to_boot_value", oka[0] and l == "A", wait=oka, ls=l, quiet_frames=q, t1_writes=await writes(t1))
        # change quickly from both tabs: must converge on ONE value, ideally the last writer's
        for gap in (0, 40, 120):
            seq = []
            for i in range(10):
                tab = t1 if i % 2 == 0 else t2
                await tab.click(f"#c{i}")
                seq.append(f"c{i}")
                if gap:
                    await asyncio.sleep(gap / 1000)
            await asyncio.sleep(2.5)  # settle first: the tabs agree transiently on an older value before the last delta lands
            okc = await _conv([t1, t2])
            q = await quiet([t1, t2])
            final = okc[1]
            record(f"C3_alternate_gap{gap}", okc[0] and q < 10, converged=okc, quiet_frames=q, last_writer_wins=(final and final[0] == "c9"))
        # back-to-back clicks in one tab
        for i in range(10):
            await t1.click(f"#c{i}", delay=0)
        await asyncio.sleep(2.5)
        okd = await _conv([t1, t2])
        q = await quiet([t1, t2])
        record("C3_back_to_back_clicks", okd[0] and okd[1][0] == "c9" and q < 10, converged=okd, quiet_frames=q)
        # three tabs, change in the middle one
        t3 = await c.page("/other", tag="t3")
        await set_in(t3, "syn", "three")
        oke = await wait_until(lambda: _conv([t1, t2, t3], want_v="three"), timeout=6)
        q = await quiet([t1, t2, t3])
        record("C3_three_tabs_follow", oke[0] and q < 10, converged=oke, quiet_frames=q)


async def _conv(pages, want_v=None):
    vs = [(await vals(p))["v-syn"] for p in pages]
    lsv = await pages[0].evaluate("() => localStorage.getItem('h4_syn')")
    allv = vs + [lsv]
    ok = len(set(allv)) == 1 and (want_v is None or allv[0] == want_v)
    return ok, allv


async def c4_sanitise(b):
    """A get_delta override that changes a value the tab just sent must reach localStorage."""
    async with Ctx(b, "C4") as c:
        await c.seed({"h4_san": "HELLO World Mixed Case", "h4_sanns": "NoSync VALUE Long"})
        t1 = await c.page("/", tag="t1")
        okb = await wait_until(lambda: _ls2(t1, {"h4_san": "hello world ", "h4_sanns": "nosync value"}), timeout=4)
        v = await vals(t1)
        record("C4_boot_sanitised_written", okb[0] and v["v-san"] == "hello world " and v["v-sanns"] == "nosync value", wait=okb, shown=[v["v-san"], v["v-sanns"]])
        await set_in(t1, "san", "ABC Upper")
        await set_in(t1, "sanns", "DEF Upper")
        okh = await wait_until(lambda: _ls2(t1, {"h4_san": "abc upper", "h4_sanns": "def upper"}), timeout=4)
        record("C4_handler_sanitised_written", okh[0], wait=okh)
        # another (non-app) tab writes a raw value: the app tab syncs it, the override changes it, storage must hold the override's output
        await writes(t1, reset=True)
        await c.seed({"h4_san": "RAW Upper"})
        okr = await wait_until(lambda: _ls2(t1, {"h4_san": "raw upper"}), timeout=4)
        v = await vals(t1)
        record("C4_synced_raw_value_sanitised_written", okr[0] and v["v-san"] == "raw upper", wait=okr, shown=v["v-san"], writes=await writes(t1))
        # two app tabs + raw write: both sanitise, converge, no storm
        t2 = await c.page("/", tag="t2")
        await c.seed({"h4_san": "XyZ TWO"})
        ok2 = await wait_until(lambda: _san_conv([t1, t2], "xyz two"), timeout=5)
        q = await quiet([t1, t2])
        record("C4_two_tabs_raw_sanitised", ok2[0] and q < 10, wait=ok2, quiet_frames=q)
        # raw write of the value the tab sent earlier ('RAW Upper'), i.e. a sent value whose echo the override replaced
        await c.seed({"h4_san": "RAW Upper"})
        ok3 = await wait_until(lambda: _san_conv([t1, t2], "raw upper"), timeout=5)
        q = await quiet([t1, t2])
        record("C4_resent_replaced_value_sanitised", ok3[0] and q < 10, wait=ok3, quiet_frames=q)
        # the tab's own handler sets the sanitised form of a pending replaced value
        await c.seed({"h4_san": "MiXeD"})
        await wait_until(lambda: _san_conv([t1, t2], "mixed"), timeout=5)
        await set_in(t1, "san", "other")
        await wait_until(lambda: _san_conv([t1, t2], "other"), timeout=5)
        await set_in(t2, "san", "mixed")
        ok4 = await wait_until(lambda: _san_conv([t1, t2], "mixed"), timeout=5)
        record("C4_set_previously_sanitised_value", ok4[0], wait=ok4)


async def _ls2(p, want_d):
    l = await ls(p)
    return all(l.get(k) == v for k, v in want_d.items()), {k: l.get(k) for k in want_d}


async def _san_conv(pages, want_v):
    vs = [(await vals(p))["v-san"] for p in pages] + [await pages[0].evaluate("() => localStorage.getItem('h4_san')")]
    return all(v == want_v for v in vs), vs


async def c6_session(b):
    async with Ctx(b, "C6") as c:
        t1 = await c.page("/", tag="t1")
        t2 = await c.page("/", tag="t2")
        await set_in(t1, "ses", "SS1")
        await asyncio.sleep(1.0)
        s1, s2 = await ss(t1), await ss(t2)
        v2 = (await vals(t2))["v-ses"]
        await t1.reload()
        await hyd(t1)
        r1 = (await vals(t1))["v-ses"]
        await set_in(t2, "ses", "SS2")
        await asyncio.sleep(1.0)
        v1 = (await vals(t1))["v-ses"]
        t3 = await c.page("/", tag="t3")
        v3 = (await vals(t3))["v-ses"]
        ok = s1.get("h4_ses") == "SS1" and "h4_ses" not in s2 and v2 == "ses-default" and r1 == "SS1" and v1 == "SS1" and v3 == "ses-default"
        record("C6_session_per_tab", ok, t1_ss=s1, t2_ss_before=s2, t2_shows=v2, t1_reload=r1, t1_after_t2=v1, new_tab=v3)


async def c7_cookie(b):
    async with Ctx(b, "C7") as c:
        t1 = await c.page("/", tag="t1")
        await set_in(t1, "ck", "CK1")
        await asyncio.sleep(1.0)
        ck1 = await c.cookies()
        await asyncio.sleep(3.0)
        await t1.reload()
        await hyd(t1)
        await asyncio.sleep(1.0)
        ck2 = await c.cookies()
        e1 = ck1.get("h4_ck", {}).get("expires")
        e2 = ck2.get("h4_ck", {}).get("expires")
        record("C7_cookie_max_age_renewed_at_boot", bool(e1 and e2 and e2 > e1), before=ck1.get("h4_ck"), after=ck2.get("h4_ck"), delta=(e2 or 0) - (e1 or 0), shown=(await vals(t1))["v-ck"])


async def c10_onload(b):
    async with Ctx(b, "C10") as c:
        t2 = await c.page("/", tag="t2")
        t1 = await c.page("/stamp", tag="t1")
        ok = await wait_until(lambda: _two(t1, t2, "v-last", "stamp@/stamp"), timeout=5)
        l = await ls(t1)
        record("C10_onload_write_stored_and_synced", ok[0] and l.get("h4_last") == "stamp@/stamp" and l.get("h4_visits") == "1", wait=ok, ls={k: l.get(k) for k in ("h4_last", "h4_visits")})
        await t1.reload()
        await hyd(t1)
        await asyncio.sleep(0.8)
        await t1.click("#nav-home")
        await asyncio.sleep(0.8)
        await t1.click("#nav-stamp")
        await asyncio.sleep(1.2)
        l = await ls(t1)
        v = await vals(t1)
        q = await quiet([t1, t2])
        record("C10_reload_and_clientnav_onload", l.get("h4_visits") == "3" and v["v-visits"] == "3", ls_visits=l.get("h4_visits"), shown=v["v-visits"], quiet_frames=q)


async def _two(a, b_, ident, want_v):
    va, vb = (await vals(a))[ident], (await vals(b_))[ident]
    return va == want_v and vb == want_v, [va, vb]


async def c11_bg_chain_empty_special(b):
    async with Ctx(b, "C11") as c:
        t1 = await c.page("/", tag="t1")
        t2 = await c.page("/other", tag="t2")
        await t1.click("#bg")
        ok = await wait_until(lambda: _conv([t1, t2], "bg-1"), timeout=5)
        l = await ls(t1)
        record("C11_background_task_write", ok[0] and l.get("h4_nos") == "bg-nos-1", wait=ok, nos=l.get("h4_nos"))
        await t1.click("#chain")
        ok = await wait_until(lambda: _conv([t1, t2], "chain-3"), timeout=5)
        l = await ls(t1)
        record("C11_yield_chain", ok[0] and l.get("h4_nos") == "chain-3-nos", wait=ok, nos=l.get("h4_nos"))
        await t1.click("#empty-back")
        ok = await wait_until(lambda: _conv([t1, t2], "chain-3-back"), timeout=5)
        l = await ls(t1)
        record("C11_empty_and_back", ok[0] and l.get("h4_nos") == "chain-3-nos-back", wait=ok, nos=l.get("h4_nos"))
        await t2.click("#to-empty")
        ok = await wait_until(lambda: _conv([t1, t2], ""), timeout=5)
        l = await ls(t1)
        await t1.reload()
        await hyd(t1)
        await asyncio.sleep(0.5)
        v = await vals(t1)
        record("C11_to_empty_persists", ok[0] and l.get("h4_nos") == "" and v["v-syn"] == "" and v["v-nos"] == "", wait=ok, ls={k: l.get(k) for k in ("h4_syn", "h4_nos")}, reload_shows=[v["v-syn"], v["v-nos"]])
        for which, val in (("uni", UNI), ("json", JSONISH), ("long", LONG)):
            await t2.click(f"#sp-{which}")
            ok = await wait_until(lambda: _conv([t1, t2], val), timeout=6)
            l = await ls(t1)
            await t1.reload()
            await hyd(t1)
            await asyncio.sleep(0.3)
            v = await vals(t1)
            q = await quiet([t1, t2], 1.5)
            record(f"C11_special_{which}", ok[0] and l.get("h4_nos") == val and v["v-syn"] == val and v["v-nos"] == val and q < 10,
                   wait=[ok[0], ok[1]], nos_ok=l.get("h4_nos") == val, reload_ok=[v["v-syn"] == val, v["v-nos"] == val], quiet_frames=q)


async def c15_component_substate_nav(b):
    async with Ctx(b, "C15") as c:
        t1 = await c.page("/", tag="t1")
        t2 = await c.page("/", tag="t2")
        await t1.fill("#box-a-in", "BOXA1")
        await t1.locator("#box-a-in").blur()
        ok = await wait_until(lambda: _two(t1, t2, "box-a-syn", "BOXA1"), timeout=5)
        v2 = await vals(t2)
        l = await ls(t1)
        boxkeys = {k: v for k, v in l.items() if "box" in k.lower()}
        record("C15_componentstate_sync_follows_nosync_not", ok[0] and v2["box-a-nos"] == "bnos-default" and v2["box-b-syn"] == "bsyn-default", wait=ok, t2=[v2["box-a-nos"], v2["box-b-syn"]], keys=boxkeys)
        await t2.reload()
        await hyd(t2)
        v2 = await vals(t2)
        record("C15_componentstate_reload", v2["box-a-syn"] == "BOXA1" and v2["box-a-nos"] == "BOXA1" and v2["box-b-nos"] == "bnos-default", t2=[v2["box-a-syn"], v2["box-a-nos"], v2["box-b-nos"]])
        await set_in(t1, "sub", "SUB1")
        ok = await wait_until(lambda: _two(t1, t2, "v-sub", "SUB1"), timeout=5)
        ck = await c.cookies()
        record("C15_substate_sync_and_cookie", ok[0] and ck.get("h4_subck", {}).get("value") == "SUB1", wait=ok, subck=ck.get("h4_subck"))
        # client-side navigation keeps everything, writes nothing extra for synced vars
        await writes(t1, reset=True)
        before = await vals(t1)
        await t1.click("#nav-other")
        await asyncio.sleep(1.0)
        await t1.click("#nav-home")
        await asyncio.sleep(1.0)
        after = await vals(t1)
        w = await writes(t1)
        record("C15_clientnav_keeps_values", before == after, writes=w, diff={k: [before[k], after[k]] for k in before if before[k] != after[k]})
        # close every tab, reopen
        lsb = await ls(t1)
        for p in (t1, t2):
            await p.close()
        t3 = await c.page("/", tag="t3")
        await asyncio.sleep(0.8)
        v3 = await vals(t3)
        l3 = await ls(t3)
        record("C15_close_reopen", l3 == lsb and v3["v-sub"] == "SUB1" and v3["box-a-syn"] == "BOXA1", ls_same=l3 == lsb, shown=[v3["v-sub"], v3["box-a-syn"], v3["v-syn"]])


async def c20_boot_writes(b):
    """Diagnostic: what a returning visitor's boot writes to storage (a3: every echo; a4: synced echoes skipped)."""
    async with Ctx(b, "C20") as c:
        await c.seed({"h4_syn": "ret-syn", "h4_nos": "ret-nos", "h4_san": "ret-san", "h4_sanns": "ret-sanns", "h4_sub": "ret-sub", "h4_last": "ret-last"})
        t1 = await c.page("/", tag="t1")
        await asyncio.sleep(1.0)
        w = await writes(t1)
        f = await frames(t1)
        v = await vals(t1)
        record("C20_returning_boot_writes", v["v-syn"] == "ret-syn" and v["v-nos"] == "ret-nos", writes=w, frames=f)


async def c21_remove_clear(b):
    """rx.remove_local_storage / rx.clear_local_storage of a synced key in tab1: what tab2, storage and reloads see (diagnostic, compared a3 vs a4)."""
    async with Ctx(b, "C21") as c:
        t1 = await c.page("/", tag="t1")
        t2 = await c.page("/", tag="t2")
        await set_in(t1, "syn", "keep-me")
        await wait_until(lambda: _conv([t1, t2], "keep-me"), timeout=5)
        await writes(t2, reset=True)
        await t1.click("#rm-syn")
        await asyncio.sleep(2.0)
        q = await quiet([t1, t2], 1.5)
        lsv = await t1.evaluate("() => localStorage.getItem('h4_syn')")
        st = {"ls": lsv, "t1": (await vals(t1))["v-syn"], "t2": (await vals(t2))["v-syn"], "t2_writes": await writes(t2), "t2_se": await t2.evaluate("() => window.__se.slice(-4)")}
        await t2.reload()
        await hyd(t2)
        st["t2_reload"] = (await vals(t2))["v-syn"]
        st["ls_after_reload"] = await t2.evaluate("() => localStorage.getItem('h4_syn')")
        record("C21_remove_synced_key", lsv is None and q < 10, quiet_frames=q, **st)
        await set_in(t1, "syn", "again")
        await wait_until(lambda: _conv([t1, t2], "again"), timeout=5)
        await t1.click("#clear-ls")
        await asyncio.sleep(2.0)
        q = await quiet([t1, t2], 1.5)
        l = await ls(t1)
        record("C21_clear_local_storage", q < 10, quiet_frames=q, ls=l, t1=(await vals(t1))["v-syn"], t2=(await vals(t2))["v-syn"])


async def c23_shared_name(b):
    """A sync=False var (Prefs.shared_ns) and a sync=True var (Sub.shared_s) on ONE storage key h4_shared."""
    async with Ctx(b, "C23") as c:
        t1 = await c.page("/", tag="t1")
        t2 = await c.page("/", tag="t2")
        await set_in(t1, "shns", "via-ns")
        ok1 = await wait_until(lambda: _lsget(t1, "h4_shared", "via-ns"), timeout=4)
        await asyncio.sleep(1.0)
        s1 = {"t1": [(await vals(t1))[k] for k in ("v-shns", "v-shs")], "t2": [(await vals(t2))[k] for k in ("v-shns", "v-shs")]}
        await set_in(t1, "shs", "via-s")
        ok2 = await wait_until(lambda: _lsget(t1, "h4_shared", "via-s"), timeout=4)
        await asyncio.sleep(1.0)
        s2 = {"t1": [(await vals(t1))[k] for k in ("v-shns", "v-shs")], "t2": [(await vals(t2))[k] for k in ("v-shns", "v-shs")]}
        # the value t1 sent at boot was "shared-default"? no: nothing stored at boot. Now t2 writes via-ns again through ns
        await set_in(t2, "shns", "via-ns")
        ok3 = await wait_until(lambda: _lsget(t2, "h4_shared", "via-ns"), timeout=4)
        await t1.reload()
        await hyd(t1)
        s3 = [(await vals(t1))[k] for k in ("v-shns", "v-shs")]
        q = await quiet([t1, t2], 1.5)
        record("C23_shared_name_sync_and_nosync", ok1[0] and ok2[0] and ok3[0] and s3 == ["via-ns", "via-ns"] and q < 10,
               ls_waits=[ok1[:2], ok2[:2], ok3[:2]], after_ns_write=s1, after_s_write=s2, t1_reload=s3, quiet_frames=q)


async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(executable_path=CHROMIUM)
        for name, fn in (("C1", c1_fresh), ("C2", c2_nosync), ("C3", c3_sync), ("C4", c4_sanitise), ("C6", c6_session),
                         ("C7", c7_cookie), ("C10", c10_onload), ("C11", c11_bg_chain_empty_special),
                         ("C15", c15_component_substate_nav), ("C20", c20_boot_writes), ("C21", c21_remove_clear),
                         ("C23", c23_shared_name)):
            if not want(name):
                continue
            try:
                await fn(b)
            except Exception as e:  # noqa: BLE001
                record(f"{name}_EXCEPTION", False, error=repr(e)[:400])
        await b.close()
    with open(OUT, "w") as fh:
        json.dump(RESULTS, fh, indent=1, ensure_ascii=False)
    n = len(RESULTS["checks"])
    bad = [k for k, v in RESULTS["checks"].items() if not v["ok"]]
    print(f"SUMMARY {n - len(bad)}/{n} pass; fail={bad}")


asyncio.run(main())
