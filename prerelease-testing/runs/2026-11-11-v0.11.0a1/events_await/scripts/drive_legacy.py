"""Drive legacyapp (decorators + failure paths) in Chromium.

usage: drive_legacy.py <frontend_url> <server_log> <out.json> [deco] [fail]
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

URL, SERVER_LOG, OUT = sys.argv[1].rstrip("/"), Path(sys.argv[2]), Path(sys.argv[3])
PARTS = sys.argv[4:] or ["deco", "fail"]

SPY = """
window.__toasts = [];
window.__hist = {};
new MutationObserver((muts) => {
  for (const m of muts) for (const n of m.addedNodes) {
    if (n.nodeType !== 1) continue;
    const els = n.matches?.('[data-sonner-toast]') ? [n] : [...(n.querySelectorAll?.('[data-sonner-toast]') ?? [])];
    for (const e of els) if (!window.__toasts.some((t) => t.el === e)) window.__toasts.push({t: Date.now(), el: e, text: ''});
  }
  for (const t of window.__toasts) if (t.el.isConnected && t.el.textContent) t.text = t.el.textContent;
  for (const id of ['result','out','a','b','c','cv','status','count','partial','done','bg','other-n']) {
    const el = document.getElementById(id); if (!el) continue;
    const h = (window.__hist[id] ??= []);
    if (!h.length || h[h.length-1][1] !== el.textContent) h.push([Date.now(), el.textContent]);
  }
}).observe(document, {childList: true, subtree: true, characterData: true});
"""
frames: list = []
console: list = []
failed: list = []
F_IDS = ["result", "a", "b", "c", "cv", "status", "count", "partial", "done", "bg", "other-n", "gated-runs"]


def snap(page, ids):
    return page.evaluate("(ids) => Object.fromEntries(ids.map(i => [i, document.getElementById(i)?.textContent ?? null]))", ids)


def toasts(page, since):
    return page.evaluate("(s) => (window.__toasts ?? []).filter(t => t.t >= s).map(t => t.text || t.el.textContent)", since * 1000)


def hist(page, since, ids=None):
    h = page.evaluate("(s) => Object.fromEntries(Object.entries(window.__hist ?? {}).map(([k, v]) => [k, v.filter(x => x[0] >= s).map(x => [Math.round(x[0] - s), x[1]])]))", since * 1000)
    return {k: v for k, v in h.items() if v and (ids is None or k in ids)}


def log_since(off):
    with SERVER_LOG.open("rb") as f:
        f.seek(off)
        return f.read().decode(errors="replace")


def sent_names(since):
    out = []
    for t, d, payload in frames:
        if t >= since and d == "sent" and '"name"' in payload:
            out.append(payload.split('"name":"')[1].split('"')[0])
    return out


def ping(page, timeout=20.0):
    """Server round trip; returns (latency or None, the server's own view of the state)."""
    before = page.evaluate("() => document.getElementById('result')?.textContent")
    t0 = time.time()
    page.click("#f-ping")
    try:
        page.wait_for_function(
            "(b) => { const t = document.getElementById('result')?.textContent ?? ''; return t.startsWith('ping@') && t !== b; }",
            arg=before, timeout=timeout * 1000,
        )
    except Exception:
        return None, None
    return round(time.time() - t0, 3), page.evaluate("() => document.getElementById('result').textContent").split(": ", 1)[1]


def deco(page, results):
    page.goto(URL + "/")
    page.wait_for_selector("#d-reset")
    time.sleep(1.5)
    results["import_results"] = json.loads(page.inner_text("#import-results"))
    ids = page.evaluate("() => [...document.querySelectorAll('[id^=d-]')].map(e => e.id)")
    results["deco_ids"] = ids
    for ident in ids:
        if ident in ("d-reset",) or ident.endswith("-err"):
            if ident.endswith("-err"):
                print(f"[deco] {ident}: {page.inner_text('#' + ident)}")
            continue
        page.click("#d-reset")
        page.wait_for_function("() => document.getElementById('out')?.textContent === 'reset'", timeout=10000)
        off = SERVER_LOG.stat().st_size
        t0 = time.time()
        page.click("#" + ident)
        time.sleep(1.2)
        name = ident[2:]
        own = page.evaluate("(i) => document.getElementById(i)?.textContent ?? null", f"out-{name}")
        r = {
            "out": page.inner_text("#out"), "own_out": own, "calls": page.inner_text("#calls"),
            "toasts": toasts(page, t0 - 0.05), "sent": sent_names(t0), "out_hist": hist(page, t0, ["out"]).get("out"),
            "log": log_since(off)[-3000:],
            "console": [c for c in console if c[0] >= t0 and c[1] in ("error", "warning", "pageerror")],
        }
        results[f"deco:{name}"] = r
        print(f"[deco] {name:20s} out={r['out']!r} own={own!r} calls={r['calls']!r} sent={[n.split('.')[-1] for n in r['sent']]} toasts={r['toasts']} log={' '.join(r['log'].split())[:260]!r}", flush=True)
    # double click: throttle + warnings per call
    off = SERVER_LOG.stat().st_size
    for _ in range(3):
        page.click("#d-above")
        time.sleep(0.3)
    results["deco:above_x3_log"] = log_since(off)
    print("[deco] above x3 extra log:", " ".join(results["deco:above_x3_log"].split())[:400])


def fail(page, results, new_page):
    page.goto(URL + "/fail")
    page.wait_for_selector("#f-reset")
    time.sleep(1.5)

    def reset():
        page.click("#f-disarm")
        time.sleep(0.3)
        page.click("#f-reset")
        page.wait_for_function("() => document.getElementById('result')?.textContent === 'reset: ok'", timeout=20000)
        time.sleep(0.2)

    def record(name, t0, off, **extra):
        lat, server = ping(page)
        r = {"client_before_ping": extra.pop("client", None) or snap(page, F_IDS), "ping_latency_s": lat, "server_view": server,
             "client_after_ping": snap(page, F_IDS), "toasts": toasts(page, t0 - 0.05), "hist_ms": hist(page, t0),
             "log": log_since(off)[-5000:], "console": [c for c in console if c[0] >= t0 and c[1] in ("error", "warning", "pageerror")], **extra}
        results[f"fail:{name}"] = r
        c = {k: v for k, v in r["client_before_ping"].items() if v not in ("", "0", None) and k != "result"}
        print(f"[fail] {name}: client(before ping)={c} ping={lat}s server={server} toasts={r['toasts']} {extra if extra else ''}", flush=True)
        h = {k: v for k, v in r["hist_ms"].items() if k not in ("result",)}
        print(f"       hist_ms={h}", flush=True)

    for name in ("raise_after_yield", "raise_no_yield", "raise_other", "ret_value", "ret_garbage", "ret_self_handler", "ret_self_handler_call", "chain", "gated_plain"):
        reset()
        off, t0 = SERVER_LOG.stat().st_size, time.time()
        page.click(f"#f-{name}")
        time.sleep(1.5)
        record(name, t0, off, client=snap(page, F_IDS), blocked=page.evaluate("() => window.__blocked || 0"))

    # supersedes: a is cancelled in its second sleep by b
    reset()
    off, t0 = SERVER_LOG.stat().st_size, time.time()
    page.click("#f-sup-a")
    time.sleep(1.5)
    page.click("#f-sup-b")
    time.sleep(0.5)
    s1 = snap(page, F_IDS)
    time.sleep(2.5)
    record("supersedes", t0, off, client=snap(page, F_IDS), client_0_5s_after_cancel=s1)

    # background task: loading the linked state fails
    reset()
    off, t0 = SERVER_LOG.stat().st_size, time.time()
    page.click("#f-bg-fail")
    time.sleep(1.0)
    record("bg_linked_load_fails", t0, off)
    # ... a second event, to see whether the lock comes back at all
    lat2, _ = ping(page)
    results["fail:bg_linked_load_fails"]["second_ping_s"] = lat2
    print(f"       second ping {lat2}s", flush=True)

    # a fresh session: on 0.10.1 the previous scenario leaves this one locked for good
    page = new_page()
    page.goto(URL + "/fail")
    page.wait_for_selector("#f-reset")
    time.sleep(1.5)

    # background task cancelled (superseded) while loading the linked state
    reset()
    off, t0 = SERVER_LOG.stat().st_size, time.time()
    page.click("#f-bg-slow")
    time.sleep(1.0)
    page.click("#f-bg-ok")
    time.sleep(1.5)
    record("bg_linked_cancelled_in_load", t0, off)
    lat2, _ = ping(page)
    results["fail:bg_linked_cancelled_in_load"]["second_ping_s"] = lat2
    print(f"       second ping {lat2}s", flush=True)

    # upload gated by middleware (fresh session again)
    page = new_page()
    page.goto(URL + "/fail")
    page.wait_for_selector("#f-reset")
    time.sleep(1.5)
    reset()
    f1 = Path(__file__).parent / "up1.txt"
    f1.write_text("hello")
    page.set_input_files("#u1 input[type=file]", [str(f1)])
    off, t0 = SERVER_LOG.stat().st_size, time.time()
    page.click("#f-gated_upload")
    time.sleep(1.5)
    record("gated_upload", t0, off, client=snap(page, F_IDS), blocked=page.evaluate("() => window.__blocked || 0"))


def main():
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")

        def on_ws(ws):
            ws.on("framereceived", lambda payload: frames.append((time.time(), "recv", str(payload))))
            ws.on("framesent", lambda payload: frames.append((time.time(), "sent", str(payload))))

        def new_page():
            page = browser.new_context().new_page()
            page.add_init_script(SPY)
            page.on("console", lambda m: console.append((time.time(), m.type, m.text)))
            page.on("pageerror", lambda e: console.append((time.time(), "pageerror", str(e))))
            page.on("response", lambda r: failed.append((time.time(), f"{r.status} {r.url}")) if r.status >= 400 else None)
            page.on("websocket", on_ws)
            return page

        page = new_page()
        try:
            if "deco" in PARTS:
                deco(page, results)
            if "fail" in PARTS:
                fail(page, results, new_page)
        finally:
            OUT.write_text(json.dumps({"results": results, "console_all": console, "failed_all": failed}, indent=1))
            browser.close()


if __name__ == "__main__":
    main()
