"""Client-storage write probe for the upgrade sweep (item 2 of the brief, #7460 re-verification).

Opens <url> in Chromium (persistent profile dir, or a throw-away context with '-'), installs an init
script BEFORE any app JS runs that
  * snapshots localStorage / sessionStorage / document.cookie at document start, and
  * logs every localStorage/sessionStorage setItem/removeItem/clear and every document.cookie write
    (key, new value, previous value),
records the first websocket frames (connect payload + first deltas), console, page errors and failed
requests, and prints a compact verdict:
  * restored      : expected text visible after load (--expect-text, repeatable)
  * kept          : the initial storage values (--keep key=value, repeatable) are unchanged at the end
  * no_writes     : no storage/cookie write at all happened during the load (--forbid-writes), or only writes
                    that leave a stored value unchanged (reported as "idempotent")
Usage:
  storage_probe.py <url> <outdir> <tag> <profile_dir|-> [--wait 8] [--expect-text T]... [--keep k=v]...
                   [--forbid-writes] [--reload] [--path /x]
Run with the driver venv:  NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python storage_probe.py ...
"""

import argparse
import json
import sys
import time
from pathlib import Path

import playwright  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

assert ("/envs/" + __import__("os").environ.get("DRIVER", "driver") + "/") in playwright.__file__, playwright.__file__
CHROMIUM = "/opt/pw-browsers/chromium"

INIT_JS = r"""
(() => {
  if (window.__qa_installed) return; window.__qa_installed = true;
  const log = (e) => { try { e.t = Math.round(performance.now()); e.path = location.pathname; window.qa_log(JSON.stringify(e)); } catch (_) {} };
  const dump = (s) => { const o = {}; try { for (let i = 0; i < s.length; i++) { const k = s.key(i); o[k] = s.getItem(k); } } catch (_) {} return o; };
  const cookies = () => { try { return document.cookie; } catch (_) { return ''; } };
  log({type: 'snapshot', when: 'doc_start', ls: dump(localStorage), ss: dump(sessionStorage), cookie: cookies()});
  const P = Storage.prototype, set = P.setItem, rem = P.removeItem, clr = P.clear;
  const which = (s) => s === window.localStorage ? 'local' : (s === window.sessionStorage ? 'session' : '?');
  P.setItem = function (k, v) { const pv = this.getItem(k); log({type: 'setItem', store: which(this), key: k, value: String(v).slice(0, 400), prev: pv === null ? null : pv.slice(0, 400), same: pv === String(v), vlen: String(v).length}); return set.apply(this, arguments); };
  P.removeItem = function (k) { log({type: 'removeItem', store: which(this), key: k, prev: this.getItem(k)}); return rem.apply(this, arguments); };
  P.clear = function () { log({type: 'clear', store: which(this)}); return clr.apply(this, arguments); };
  try {
    const d = Object.getOwnPropertyDescriptor(Document.prototype, 'cookie');
    Object.defineProperty(document, 'cookie', {configurable: true,
      get() { return d.get.call(document); },
      set(v) { log({type: 'cookie', value: String(v).slice(0, 400), prev_cookie_header: d.get.call(document).slice(0, 600)}); d.set.call(document, v); }});
  } catch (e) { log({type: 'cookie_hook_failed', err: String(e)}); }
})();
"""


class Probe:
    """Collects storage writes, ws frames, console and network failures for one browser context."""

    def __init__(self):
        self.writes = []
        self.ws = []
        self.console = []
        self.errors = []
        self.bad = []

    def log_cb(self, s):
        try:
            self.writes.append(json.loads(s))
        except Exception:  # noqa: BLE001
            self.writes.append({"type": "unparsable", "raw": str(s)[:200]})

    def attach_ctx(self, ctx):
        ctx.expose_function("qa_log", self.log_cb)
        ctx.add_init_script(INIT_JS)

    def attach_page(self, page):
        t0 = time.time()
        page.on("console", lambda m: self.console.append({"t": round(time.time() - t0, 2), "type": m.type, "text": m.text[:400]}))
        page.on("pageerror", lambda e: self.errors.append(str(e)[:400]))

        def resp(r):
            if r.status >= 400:
                self.bad.append({"url": r.url, "status": r.status})

        page.on("response", resp)
        page.on("requestfailed", lambda r: self.bad.append({"url": r.url, "failure": r.failure}))

        def on_ws(ws):
            if "_event" not in ws.url:
                return
            ws.on("framesent", lambda p: self.ws.append({"t": round(time.time() - t0, 2), "dir": "sent", "data": (p if isinstance(p, str) else repr(p))[:3000]}))
            ws.on("framereceived", lambda p: self.ws.append({"t": round(time.time() - t0, 2), "dir": "recv", "data": (p if isinstance(p, str) else repr(p))[:3000]}))

        page.on("websocket", on_ws)


def storage_now(page):
    return page.evaluate(
        """() => { const d = (s) => { const o = {}; for (let i = 0; i < s.length; i++) { const k = s.key(i); o[k] = s.getItem(k); } return o; };
        return {ls: d(localStorage), ss: d(sessionStorage), cookie: document.cookie}; }"""
    )


def classify_writes(writes):
    """Split logged writes into changing vs idempotent (value equal to the previous one)."""
    changing, idem = [], []
    for w in writes:
        if w["type"] == "setItem":
            (idem if w.get("same") else changing).append(w)
        elif w["type"] in ("removeItem", "clear"):
            changing.append(w)
        elif w["type"] == "cookie":
            v = w["value"]
            name, _, rest = v.partition("=")
            val = rest.split(";", 1)[0]
            hdr = w.get("prev_cookie_header", "")
            prev = {c.split("=", 1)[0].strip(): c.split("=", 1)[1] for c in hdr.split("; ") if "=" in c}
            w["cookie_name"], w["cookie_val"], w["prev_val"] = name, val, prev.get(name)
            expired = "expires=Thu, 01 Jan 1970" in v or "max-age=0" in v.lower()
            (idem if (prev.get(name) == val and not expired) else changing).append(w)
    return changing, idem


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("outdir")
    ap.add_argument("tag")
    ap.add_argument("profile")
    ap.add_argument("--wait", type=float, default=8.0)
    ap.add_argument("--expect-text", action="append", default=[])
    ap.add_argument("--keep", action="append", default=[], help="key=value that must be unchanged (localStorage key or cookie name)")
    ap.add_argument("--forbid-writes", action="store_true")
    ap.add_argument("--reload", action="store_true")
    ap.add_argument("--path", default="")
    a = ap.parse_args()
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    pr = Probe()
    res = {"tag": a.tag, "url": a.url, "args": vars(a), "checks": []}

    def check(name, ok, detail=""):
        res["checks"].append({"name": name, "status": "pass" if ok else "fail", "detail": str(detail)[:500]})
        print(("PASS " if ok else "FAIL ") + name, "|", str(detail)[:300])

    with sync_playwright() as p:
        if a.profile == "-":
            browser = p.chromium.launch(executable_path=CHROMIUM)
            ctx = browser.new_context()
        else:
            browser = None
            ctx = p.chromium.launch_persistent_context(a.profile, executable_path=CHROMIUM)
        pr.attach_ctx(ctx)
        res["cookies_before"] = ctx.cookies()
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        pr.attach_page(page)
        page.goto(a.url.rstrip("/") + a.path, wait_until="load")
        time.sleep(a.wait)
        res["end"] = storage_now(page)
        res["body_text"] = page.inner_text("body")[:1500]
        page.screenshot(path=str(out / f"{a.tag}.jpg"), type="jpeg", quality=55)
        res["cookies_after"] = ctx.cookies()
        mark = len(pr.writes)
        if a.reload:
            page.reload(wait_until="load")
            time.sleep(a.wait)
            res["end_after_reload"] = storage_now(page)
            res["writes_in_reload"] = pr.writes[mark:]
        ctx.close()
        if browser:
            browser.close()

    starts = [w for w in pr.writes if w["type"] == "snapshot"]
    res["doc_start"] = starts[0] if starts else None
    first_load_writes = [w for w in pr.writes[:mark] if w["type"] != "snapshot"]
    changing, idem = classify_writes(first_load_writes)
    idem_counts = {}
    for w in idem:
        k = f'{w["type"]} {w.get("key") or w.get("cookie_name")}'
        idem_counts[k] = idem_counts.get(k, 0) + 1
    res["writes_idempotent_counts"] = idem_counts
    res["writes_total"] = len(first_load_writes)
    res["writes"] = first_load_writes[:150]
    fw = {"token", "theme", "last_compiled_theme", "debug"}
    app_changing = [w for w in changing if (w.get("key") or w.get("cookie_name")) not in fw]
    res["writes_changing"] = changing
    res["writes_changing_app"] = app_changing
    res["writes_idempotent"] = idem
    res["ws"] = pr.ws[:40]
    res["console"] = pr.console
    res["pageerrors"] = pr.errors
    res["bad_requests"] = pr.bad
    for t in a.expect_text:
        check(f"text visible: {t!r}", t in res["body_text"], res["body_text"][:120].replace("\n", " | "))
    ds = res["doc_start"] or {"ls": {}, "ss": {}, "cookie": ""}
    ck_start = {c.split("=", 1)[0]: c.split("=", 1)[1] for c in ds["cookie"].split("; ") if "=" in c}
    ck_end = {c.split("=", 1)[0]: c.split("=", 1)[1] for c in res["end"]["cookie"].split("; ") if "=" in c}
    for kv in a.keep:
        k, _, v = kv.partition("=")
        src_start = {**ds["ls"], **ck_start}.get(k)
        src_end = {**res["end"]["ls"], **ck_end}.get(k)
        check(f"kept {k}", src_start == v and src_end == v, f"start={src_start!r} end={src_end!r}")
    if a.forbid_writes:
        check("no CHANGING app storage/cookie writes during first load (framework keys token/theme/last_compiled_theme/debug ignored)", not app_changing, [(w["type"], w.get("key") or w.get("cookie_name"), (w.get("value") or "")[:60]) for w in app_changing])
    res["summary"] = {
        "doc_start_ls_keys": sorted(ds["ls"]),
        "doc_start_cookie_names": sorted(ck_start),
        "end_ls_keys": sorted(res["end"]["ls"]),
        "end_ss_keys": sorted(res["end"]["ss"]),
        "end_cookie_names": sorted(ck_end),
        "n_writes": len(first_load_writes),
        "n_changing": len(changing),
        "n_changing_app": len(app_changing),
        "n_idempotent": len(idem),
        "console_errors": [c["text"][:160] for c in pr.console if c["type"] in ("error", "warning")],
        "pageerrors": pr.errors,
        "bad_requests": pr.bad,
    }
    res["summary"]["idempotent_counts"] = idem_counts
    (out / f"{a.tag}.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res["summary"], indent=1))
    for w in changing[:40]:
        print("CHANGING WRITE:", w["type"], w.get("key") or w.get("cookie_name"), "prev=", repr(w.get("prev") if "prev" in w else w.get("prev_val"))[:60], "new=", repr(w.get("value"))[:80])
    if len(changing) > 40:
        print(f"... {len(changing) - 40} more changing writes")
    for k, n in idem_counts.items():
        print(f"idempotent write x{n}: {k}")
    sys.exit(1 if any(c["status"] == "fail" for c in res["checks"]) else 0)


if __name__ == "__main__":
    main()
