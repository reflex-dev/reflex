#!/usr/bin/env python
"""Independent Playwright driver for verifying events-cluster claims E-1 / E-2.

Run with the `driver` venv python, from a neutral directory:

  NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
    $SB/envs/driver/bin/python drive_verify.py --base http://localhost:3640 \
        --label alpha2_dev_disk --out $W/out/alpha2_dev_disk --cases direct,gen

Per case it opens a FRESH browser context (fresh client token, fresh state), loads the page,
waits for hydration, performs the scenario, and records
  * in-page timeline (performance clock -> epoch ms): WebSocket send/recv frames, clicks,
    changes of the displayed state variables (MutationObserver), sonner toast nodes,
  * Playwright/CDP websocket frames with host timestamps (second, independent source),
  * console / pageerror / failed requests / 4xx-5xx responses,
  * DOM snapshots at checkpoints:  before | t1 (settle seconds after the failing event, no other
    event sent) | t2 (after an unrelated `ping` click) | t3 (after a page reload = server truth).
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

assert "/envs/driver" in sys.prefix, f"run me with the driver venv python, got {sys.prefix}"

from playwright.async_api import async_playwright  # noqa: E402

IDS = [
    "hyd",
    "v-status",
    "v-spinner",
    "v-pings",
    "v-log",
    "v-other",
    "v-load_note",
    "v-echo_backend",
    "v-mode",
]

INIT_JS = r"""
(() => {
  if (window.__evv) return;
  const now = () => performance.timeOrigin + performance.now();
  const E = (window.__evv = { rows: [] });
  const add = (kind, detail) => E.rows.push(Object.assign({ ts: now(), kind }, detail));
  const OrigWS = window.WebSocket;
  function WS(url, protocols) {
    const ws = protocols === undefined ? new OrigWS(url) : new OrigWS(url, protocols);
    const wsid = (E.nws = (E.nws || 0) + 1);
    const ev = String(url).indexOf('/_event') >= 0;
    add('ws-new', { url: String(url), wsid, ev });
    ws.addEventListener('open', () => add('ws-open', { wsid, ev }));
    ws.addEventListener('close', (e) => add('ws-close', { code: e.code, wsid, ev }));
    ws.addEventListener('message', (e) =>
      add('ws-recv', { wsid, ev, data: typeof e.data === 'string' ? e.data : '[binary]' }));
    const send = ws.send.bind(ws);
    ws.send = (d) => { add('ws-send', { wsid, ev, data: typeof d === 'string' ? d : '[binary]' }); return send(d); };
    return ws;
  }
  WS.prototype = OrigWS.prototype;
  WS.CONNECTING = 0; WS.OPEN = 1; WS.CLOSING = 2; WS.CLOSED = 3;
  window.WebSocket = WS;
  document.addEventListener('click', (e) => {
    const t = e.target && e.target.closest ? e.target.closest('[id]') : null;
    add('click', { id: t ? t.id : null });
  }, true);
  const watched = %IDS%;
  const last = {};
  const snap = () => { const o = {}; for (const id of watched) { const el = document.getElementById(id); o[id] = el ? el.textContent : null; } return o; };
  window.__evv_snap = snap;
  const check = () => {
    const s = snap();
    for (const id of watched) {
      if (s[id] !== last[id]) {
        if (id in last || s[id] !== null) add('dom', { id, value: s[id], prev: id in last ? last[id] : null });
        last[id] = s[id];
      }
    }
    const toasts = document.querySelectorAll('[data-sonner-toast]');
    const n = toasts.length;
    const texts = Array.from(toasts).map((x) => (x.textContent || '').slice(0, 160));
    const sig = n + '|' + texts.join('~');
    if (sig !== last.__toast_sig) { add('toast', { count: n, text: texts }); last.__toast_sig = sig; }
  };
  new MutationObserver(check).observe(document, { subtree: true, childList: true, characterData: true });
})();
""".replace("%IDS%", json.dumps(IDS))


def parse_sio(data: str):
    """Parse a socket.io text frame ("42/_event,[...]" or "42[...]") -> (event_name, payload) or None."""
    if not isinstance(data, str) or not data.startswith("42"):
        return None
    body = data[2:]
    if body.startswith("/"):
        body = body.split(",", 1)[1] if "," in body else ""
    try:
        arr = json.loads(body)
    except Exception:
        return None
    if not isinstance(arr, list) or not arr:
        return None
    name = arr[0]
    payload = arr[1] if len(arr) > 1 else None
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            pass
    return name, payload


def flat_delta(delta):
    """{state_path: {var_rx_state_: value}} -> {"state.var": value} with generated suffixes stripped."""
    out = {}
    if not isinstance(delta, dict):
        return out
    for st, vals in delta.items():
        short = st.split(".")[-1].split("___")[-1] if st else st
        if isinstance(vals, dict):
            for k, v in vals.items():
                k = k[: -len("_rx_state_")] if k.endswith("_rx_state_") else k
                out[f"{short}.{k}"] = v
    return out


def summarize_row(r, t_ref):
    """Compact one in-page row for the timeline."""
    dt = round(r["ts"] - t_ref, 1)
    k = r["kind"]
    if k == "ws-recv":
        p = parse_sio(r["data"])
        if p is None:
            return {"dt_ms": dt, "kind": "ws-recv", "raw": r["data"][:60]}
        name, payload = p
        d = {"dt_ms": dt, "kind": "ws-recv", "sio": name}
        if isinstance(payload, dict):
            fd = flat_delta(payload.get("delta"))
            if fd:
                d["delta"] = fd
            ev = payload.get("events") or []
            if ev:
                d["events"] = [e.get("name") for e in ev]
                d["toast"] = "toast" in json.dumps(ev).lower()
            if "final" in payload:
                d["final"] = payload["final"]
        return d
    if k == "ws-send":
        p = parse_sio(r["data"])
        if p is None:
            return {"dt_ms": dt, "kind": "ws-send", "raw": r["data"][:60]}
        name, payload = p
        d = {"dt_ms": dt, "kind": "ws-send", "sio": name}
        if isinstance(payload, dict):
            d["event"] = payload.get("name")
            if payload.get("payload"):
                d["payload"] = payload["payload"]
        return d
    if k == "click":
        return {"dt_ms": dt, "kind": "click", "id": r.get("id")}
    if k == "dom":
        return {"dt_ms": dt, "kind": "dom", "id": r["id"], "value": r["value"], "prev": r["prev"]}
    if k == "toast":
        return {"dt_ms": dt, "kind": "toast", "count": r["count"], "text": r["text"]}
    return {"dt_ms": dt, "kind": k, **{x: y for x, y in r.items() if x not in ("ts", "kind")}}


class Rec:
    """Per-case recorder."""

    def __init__(self):
        self.cdp = []  # (epoch_ms, dir, payload)
        self.console = []
        self.pageerrors = []
        self.failed = []
        self.bad_resp = []
        self.dialogs = []
        self.segments = []  # in-page rows per document (fetched before reloads / at end)
        self.marks = []  # (epoch_ms, label)

    def mark(self, label):
        self.marks.append((time.time() * 1000, label))


def attach(page, rec: Rec):
    def on_ws(ws):
        ws.on("framereceived", lambda p: rec.cdp.append((time.time() * 1000, "recv", p if isinstance(p, str) else "[binary]")))
        ws.on("framesent", lambda p: rec.cdp.append((time.time() * 1000, "send", p if isinstance(p, str) else "[binary]")))
        ws.on("close", lambda *_: rec.cdp.append((time.time() * 1000, "close", "")))

    page.on("websocket", on_ws)
    page.on("console", lambda m: rec.console.append({"ts": time.time() * 1000, "type": m.type, "text": m.text[:400]}))
    page.on("pageerror", lambda e: rec.pageerrors.append({"ts": time.time() * 1000, "text": str(e)[:400]}))
    page.on("requestfailed", lambda r: rec.failed.append({"ts": time.time() * 1000, "url": r.url[:160], "err": r.failure}))
    page.on("response", lambda r: rec.bad_resp.append({"ts": time.time() * 1000, "url": r.url[:160], "status": r.status}) if r.status >= 400 else None)

    async def on_dialog(d):
        rec.dialogs.append({"ts": time.time() * 1000, "type": d.type, "message": d.message[:200]})
        await d.accept()

    page.on("dialog", on_dialog)


async def snap(page):
    return await page.evaluate("() => window.__evv_snap ? window.__evv_snap() : null")


async def grab_rows(page):
    return await page.evaluate("() => window.__evv ? window.__evv.rows : []")


async def wait_hydrated(page, timeout=90):
    await page.wait_for_function(
        "() => { const e = document.getElementById('hyd'); return e && e.textContent === 'yes'; }",
        timeout=timeout * 1000,
    )


async def click(page, rec: Rec, bid: str):
    rec.mark(f"click:{bid}")
    await page.click(f"#{bid}", timeout=20000)


async def checkpoint(page, rec, snaps, name, shots, out: Path, case: str, shot: bool):
    snaps[name] = await snap(page)
    snaps[name]["_epoch_ms"] = time.time() * 1000
    if shot:
        p = out / f"{case}_{name}.png"
        await page.screenshot(path=str(p))
        shots.append(p.name)


async def run_case(browser, args, case: str, spec: dict, out: Path):
    rec = Rec()
    ctx = await browser.new_context(viewport={"width": 1280, "height": 1300})
    await ctx.add_init_script(INIT_JS)
    page = await ctx.new_page()
    attach(page, rec)
    snaps, shots = {}, []
    shot = case in args.shots.split(",") or args.shots == "all"
    t_case0 = time.time() * 1000
    err = None
    try:
        start_url = args.base + spec.get("start", "/")
        await page.goto(start_url, wait_until="domcontentloaded")
        if spec.get("wait_hydrated", True):
            await wait_hydrated(page)
        await asyncio.sleep(0.4)
        await checkpoint(page, rec, snaps, "before", shots, out, case, shot)
        mode = spec.get("exc_mode")
        if mode and mode != "default":
            await click(page, rec, f"btn-mode_{mode}")
            await asyncio.sleep(0.8)
            await checkpoint(page, rec, snaps, "after_mode", shots, out, case, False)
        rec.mark("scenario-start")
        t_scn0 = time.time() * 1000
        for step in spec.get("steps", []):
            bid, delay = step
            await click(page, rec, bid)
            await asyncio.sleep(delay)
        if spec.get("nav_wait"):
            await asyncio.sleep(spec["nav_wait"])
        await asyncio.sleep(spec.get("settle", args.settle))
        await checkpoint(page, rec, snaps, "t1", shots, out, case, shot)
        if spec.get("ping", True):
            rec.mark("ping")
            await click(page, rec, "btn-ping")
            await asyncio.sleep(1.5)
            await checkpoint(page, rec, snaps, "t2", shots, out, case, shot)
        # a second, independent "next event" to see whether anything else is still pending
        rec.segments.append({"label": "doc1", "rows": await grab_rows(page)})
        rec.mark("reload")
        await page.reload(wait_until="domcontentloaded")
        await wait_hydrated(page)
        await asyncio.sleep(1.0)
        await checkpoint(page, rec, snaps, "t3", shots, out, case, shot)
        for extra in spec.get("after_reload", []):
            await click(page, rec, extra)
            await asyncio.sleep(1.0)
        if spec.get("after_reload"):
            await checkpoint(page, rec, snaps, "t4", shots, out, case, False)
        rec.segments.append({"label": "doc2", "rows": await grab_rows(page)})
    except Exception as e:  # keep partial data
        err = f"{type(e).__name__}: {e}"
        try:
            rec.segments.append({"label": "doc_err", "rows": await grab_rows(page)})
        except Exception:
            pass
    finally:
        await ctx.close()

    # ---- build the report for this case
    marks = rec.marks
    t_first_click = next((t for t, l in marks if l.startswith("click:") and not l.startswith("click:btn-mode_")), None)
    t_ping = next((t for t, l in marks if l == "ping"), None)
    # in-page timeline for doc1 relative to the first scenario click (in-page clock)
    doc1 = next((s["rows"] for s in rec.segments if s["label"] == "doc1"), [])
    first_click_row = None
    scn_start = next((t for t, l in marks if l == "scenario-start"), None)
    for r in doc1:
        if r["kind"] == "click" and r.get("id") and not str(r["id"]).startswith("btn-mode_") and (scn_start is None or r["ts"] >= scn_start - 5):
            first_click_row = r
            break
    if spec.get("start", "/") != "/" or spec.get("no_click"):
        t_ref = next((r["ts"] for r in doc1 if r["kind"] == "ws-new"), t_case0)
        if spec.get("nav_from_index"):
            t_ref = first_click_row["ts"] if first_click_row else t_ref
    else:
        t_ref = first_click_row["ts"] if first_click_row else (t_first_click or t_case0)
    timeline = []
    for seg in rec.segments:
        seen_toast = False
        for r in seg["rows"]:
            if r["kind"] in ("ws-recv", "ws-send", "ws-open", "ws-close", "ws-new") and not r.get("ev"):
                continue  # vite HMR socket
            if r["kind"] == "toast":
                if r["count"] == 0 and not seen_toast:
                    continue
                seen_toast = seen_toast or r["count"] > 0
            if r["kind"] in ("ws-recv", "ws-send", "click", "dom", "toast", "ws-open", "ws-close", "ws-new"):
                srow = summarize_row(r, t_ref)
                srow["doc"] = seg["label"]
                timeline.append(srow)
    timeline.sort(key=lambda x: x["dt_ms"])
    # keep timeline compact: drop keepalive frames
    timeline = [t for t in timeline if not (t["kind"] == "ws-recv" and t.get("raw") in ("2", "3"))]
    (out / f"{args.label}_{case}_rows.json").write_text(json.dumps([{"label": sg["label"], "rows": sg["rows"]} for sg in rec.segments]))
    cdp = [
        {"dt_ms": round(t - t_ref, 1), "dir": d, "payload": (p[:600] if isinstance(p, str) else p)}
        for (t, d, p) in rec.cdp
    ]
    report = {
        "case": case,
        "label": args.label,
        "error": err,
        "t_ref_epoch_ms": t_ref,
        "marks": [{"dt_ms": round(t - t_ref, 1), "label": l} for t, l in marks],
        "snapshots": snaps,
        "screenshots": shots,
        "timeline": timeline,
        "cdp_frames": cdp,
        "console": [dict(c, ts=round(c["ts"] - t_ref, 1)) for c in rec.console],
        "pageerrors": [dict(c, ts=round(c["ts"] - t_ref, 1)) for c in rec.pageerrors],
        "requestfailed": [dict(c, ts=round(c["ts"] - t_ref, 1)) for c in rec.failed],
        "bad_responses": [dict(c, ts=round(c["ts"] - t_ref, 1)) for c in rec.bad_resp],
        "dialogs": [dict(c, ts=round(c["ts"] - t_ref, 1)) for c in rec.dialogs],
    }
    return report


# ---- scenario table -------------------------------------------------------------------------
CASES = {
    # foreground handlers that mutate then raise
    "direct": dict(steps=[("btn-direct_raise", 0.0)]),
    "async": dict(steps=[("btn-async_raise", 0.0)]),
    "clean": dict(steps=[("btn-raise_clean", 0.0)]),
    "backend": dict(steps=[("btn-backend_raise", 0.0)], after_reload=["btn-show_backend"]),
    "chain": dict(steps=[("btn-chain_a", 0.0)]),
    "gen": dict(steps=[("btn-gen_raise", 0.0)]),
    "agen": dict(steps=[("btn-agen_raise", 0.0)]),
    "spinner": dict(steps=[("btn-spinner_finally", 0.0)]),
    "caught": dict(steps=[("btn-caught", 0.0)]),
    # background tasks
    "bg_inside": dict(steps=[("btn-bg_raise_inside", 0.0)]),
    "bg_two": dict(steps=[("btn-bg_two_blocks", 0.0)]),
    "bg_after": dict(steps=[("btn-bg_raise_after", 0.0)]),
    # superseding handlers: a, wait 0.5 s (a is past its first yield and sleeping), b
    "sup_same": dict(steps=[("btn-sup_same_a", 0.5), ("btn-sup_same_b", 0.0)], settle=3.5),
    "sup_split": dict(steps=[("btn-sup_split_a", 0.5), ("btn-sup_split_b", 0.0)], settle=3.5),
    # on_load paths
    "onload_initial": dict(start="/onload", no_click=True, settle=3.0),
    "onload_nav": dict(steps=[("btn-nav_onload", 0.0)], nav_from_index=True, settle=3.0, wait_hydrated=True),
    # no further event for a long time: does anything ever flush the stale state by itself?
    "idle40": dict(steps=[("btn-direct_raise", 0.0)], settle=40.0),
    # exception-handler variants (the mode is switched at runtime through a button)
    "direct_alert": dict(steps=[("btn-direct_raise", 0.0)], exc_mode="alert"),
    "direct_none": dict(steps=[("btn-direct_raise", 0.0)], exc_mode="none"),
    "direct_chain": dict(steps=[("btn-direct_raise", 0.0)], exc_mode="chain"),
    "gen_chain": dict(steps=[("btn-gen_raise", 0.0)], exc_mode="chain"),
    "spinner_chain": dict(steps=[("btn-spinner_finally", 0.0)], exc_mode="chain"),
}

DEFAULT_ORDER = [
    "direct", "async", "clean", "backend", "chain", "gen", "agen", "spinner", "caught",
    "bg_inside", "bg_two", "bg_after", "sup_same", "sup_split", "onload_initial", "onload_nav",
]


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cases", default=",".join(DEFAULT_ORDER))
    ap.add_argument("--settle", type=float, default=3.0)
    ap.add_argument("--shots", default="direct,gen,spinner,sup_split,bg_inside", help="comma list or 'all' or ''")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    names = [c for c in args.cases.split(",") if c]
    results = {"label": args.label, "base": args.base, "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "cases": {}}
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium", headless=True)
        results["browser"] = browser.version
        for name in names:
            spec = CASES[name]
            t0 = time.time()
            rep = await run_case(browser, args, name, spec, out)
            rep["wall_s"] = round(time.time() - t0, 1)
            results["cases"][name] = rep
            (out / f"{args.label}_report.json").write_text(json.dumps(results, indent=1))
            s = rep["snapshots"]
            g = lambda k, i: (s.get(k) or {}).get(i)  # noqa: E731
            print(
                f"[{args.label}] {name:15s} err={rep['error']} "
                f"status: before={g('before','v-status')!r} t1={g('t1','v-status')!r} t2={g('t2','v-status')!r} t3={g('t3','v-status')!r} | "
                f"log t1={g('t1','v-log')!r} t2={g('t2','v-log')!r} t3={g('t3','v-log')!r} | "
                f"spinner t1={g('t1','v-spinner')!r} t3={g('t3','v-spinner')!r} | other t1={g('t1','v-other')!r} t3={g('t3','v-other')!r} | "
                f"load_note t1={g('t1','v-load_note')!r} t3={g('t3','v-load_note')!r}",
                flush=True,
            )
        await browser.close()
    results["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (out / f"{args.label}_report.json").write_text(json.dumps(results, indent=1))


if __name__ == "__main__":
    asyncio.run(main())
