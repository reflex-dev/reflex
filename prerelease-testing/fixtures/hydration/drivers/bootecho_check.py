"""a3_hydration driver for src/bootecho (reflex#7493 boot echo).

Usage: bootecho_check.py BASE SERVER_LOG OUT_JSON
Scenarios (each in its own browser context unless noted):
  fresh_index / fresh_onload / fresh_plainload : fresh profile, what is written to LS/SS/cookies?
  user_set      : click set-user, set-user-sub, box a/b choose, good-tok; then reload x2 (values kept? frames? GD calls?)
  cookie_slide  : cookie expiry before/after a reload (is the cookie rewritten at boot?)
  bad_tok       : localStorage be_tok='bad-xyz' then reload -> sanitising get_delta override must reach the browser
  server_wins   : browser has be_srv/be_srv_ck='browser-old' -> load /onload -> on_load value must win
  cv_boot       : browser has be_theme='blue', be_note='hello', be_sub_ls='subval' -> computed vars right after boot
  nav           : client-side navigation / -> /onload -> /plainload -> / (frames + storage)
For every load: inbound delta count/bytes, per-var occurrence counts, storage dump, UI values, BOOTTRACE lines
(get_delta override calls) for this tab's token from the server log, console errors/warnings, failed requests.
"""
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

import os  # noqa: E402
assert f"/envs/{os.environ.get('DRV_VENV', 'driver')}/" in sys.executable, sys.executable
CHROMIUM = "/opt/pw-browsers/chromium"
BASE, LOG, OUT = sys.argv[1].rstrip("/"), Path(sys.argv[2]), sys.argv[3]
ROOT = "reflex___state____state"
IDS = ["hyd-flag", "theme", "note", "sess", "ck", "ckopt", "theme-upper", "note-len", "ck-combo", "sub-ls", "sub-ck",
       "sub-combo", "tok", "tok-ok", "srv-ls", "srv-ck", "clicks", "box-a-pref", "box-a-bck", "box-b-pref", "box-b-bck"]
BENIGN = ("Hey developer", "React DevTools", "[vite]", "Download the React DevTools")


def decode(p):
    if not isinstance(p, str):
        return None
    if len(p) > 2 and p[0] == "4" and p[2:3] == "/":
        comma = p.find(",", 2)
        p = p[:2] + (p[comma + 1:] if comma != -1 else "")
    if p.startswith("42"):
        try:
            return ("event", json.loads(p[2:]))
        except Exception:
            return ("event-trunc", p[:300])
    if p.startswith("40"):
        try:
            return ("connect", json.loads(p[2:]) if len(p) > 2 else None)
        except Exception:
            return ("connect-trunc", p[:300])
    return ("other", p[:40])


class Tab:
    def __init__(self, ctx, tag):
        self.ctx, self.tag = ctx, tag
        self.page = ctx.new_page()
        self.frames, self.console, self.failed, self.errors = [], [], [], []
        self.t0 = time.time()
        self.page.on("websocket", self._ws)
        self.page.on("console", lambda m: self.console.append(f"{m.type}: {m.text[:300]}"))
        self.page.on("pageerror", lambda e: self.errors.append(str(e)[:300]))
        self.page.on("requestfailed", lambda r: self.failed.append(f"{r.url} {r.failure}"))
        self.page.on("response", lambda r: r.status >= 400 and self.failed.append(f"HTTP {r.status} {r.url}"))

    def _ws(self, ws):
        if "_event" not in ws.url:
            return
        ws.on("framesent", lambda p: self.frames.append(("out", time.time() - self.t0, p)))
        ws.on("framereceived", lambda p: self.frames.append(("in", time.time() - self.t0, p)))

    def mark(self):
        return len(self.frames), len(self.console), len(self.failed), len(self.errors), LOG.stat().st_size

    def wait_hyd(self, timeout_s=30):
        for _ in range(timeout_s * 10):
            try:
                if self.page.inner_text("#hyd-flag", timeout=200) == "H:yes":
                    return True
            except Exception:
                pass
            self.page.wait_for_timeout(100)
        return False

    def ui(self):
        out = {}
        for i in IDS:
            try:
                out[i] = self.page.inner_text(f"#{i}", timeout=300)
            except Exception:
                out[i] = None
        return out

    def storage(self):
        st = self.page.evaluate("""() => ({
            local: Object.fromEntries(Object.keys(localStorage).sort().map(k => [k, localStorage.getItem(k)])),
            session: Object.fromEntries(Object.keys(sessionStorage).sort().filter(k => k !== 'token').map(k => [k, sessionStorage.getItem(k)])),
            token: sessionStorage.getItem('token')})""")
        st["cookies"] = {c["name"]: {"value": c["value"], "expires": round(c["expires"], 1), "sameSite": c["sameSite"], "path": c["path"]}
                         for c in self.ctx.cookies()}
        return st

    def summarize(self, m, label):
        f0, c0, x0, e0, l0 = m
        deltas, out_events, n_in, b_in, n_out, b_out = [], [], 0, 0, 0, 0
        var_counts = {}
        for d, t, p in self.frames[f0:]:
            if not isinstance(p, str):
                continue
            k = decode(p)
            if d == "in":
                n_in += 1
                b_in += len(p)
            else:
                n_out += 1
                b_out += len(p)
            if k is None:
                continue
            kind, payload = k
            if kind == "connect" and d == "out" and isinstance(payload, dict):
                ev = payload.get("event") or {}
                out_events.append({"connect": ev.get("name", "").split(".")[-1], "vars": (ev.get("payload") or {}).get("vars")})
            elif kind == "event" and isinstance(payload, list) and len(payload) > 1 and isinstance(payload[1], dict):
                upd = payload[1]
                if d == "in" and "delta" in upd:
                    delta = upd.get("delta") or {}
                    root = delta.get(ROOT, {})
                    item = {"t": round(t, 3), "len": len(p), "root_is_h": root.get("is_hydrated_rx_state_", "-"),
                            "vars": {}}
                    for s, v in delta.items():
                        if not isinstance(v, dict):
                            continue
                        short = s.split(".")[-1]
                        for kk, vv in v.items():
                            if kk.startswith("rx_router") or kk in ("is_hydrated_rx_state_",):
                                continue
                            name = f"{short}.{kk.removesuffix('_rx_state_')}"
                            item["vars"][name] = vv
                            var_counts[name] = var_counts.get(name, 0) + 1
                    deltas.append(item)
                elif d == "out" and "name" in upd:
                    out_events.append({"event": upd["name"].split(".")[-1], "payload": upd.get("payload")})
        st = self.storage()
        tok8 = (st.get("token") or "")[:8]
        with LOG.open("rb") as fh:
            fh.seek(l0)
            new = fh.read().decode("utf-8", "replace")
        traces = []
        for line in new.splitlines():
            if "BOOTTRACE" in line and f'"tok": "{tok8}"' in line:
                traces.append(line[line.index("BOOTTRACE") + 10:][:600])
        cons = [c for c in self.console[c0:] if c.startswith(("error", "warning")) and not any(b in c for b in BENIGN)]
        return {"label": label, "tab": self.tag, "ui": self.ui(), "storage": st, "deltas": deltas,
                "n_deltas": len(deltas), "frames_in": n_in, "bytes_in": b_in, "frames_out": n_out, "bytes_out": b_out,
                "out_events": out_events, "var_counts": var_counts, "gd_traces": traces,
                "gd_calls": {s: sum(1 for t in traces if t.startswith("GD") and f'"st": "{s}"' in t) for s in ("Prefs", "SubPrefs", "Guard")},
                "console": cons, "failed": self.failed[x0:], "pageerrors": self.errors[e0:]}

    def load(self, path, label, settle=1500):
        m = self.mark()
        self.page.goto(BASE + path)
        h = self.wait_hyd()
        self.page.wait_for_timeout(settle)
        r = self.summarize(m, label)
        r["hydrated"] = h
        return r

    def reload(self, label, settle=1500):
        m = self.mark()
        self.page.reload()
        h = self.wait_hyd()
        self.page.wait_for_timeout(settle)
        r = self.summarize(m, label)
        r["hydrated"] = h
        return r

    def click(self, sel, label, settle=800):
        m = self.mark()
        self.page.click(sel)
        self.page.wait_for_timeout(settle)
        return self.summarize(m, label)


def brief(r):
    st = r["storage"]
    ls = {k: v for k, v in st["local"].items() if k not in ("theme", "last_compiled_theme")}
    return (f"[{r['label']}] H={r.get('hydrated')} deltas={r['n_deltas']} in={r['frames_in']}f/{r['bytes_in']}B "
            f"out={r['frames_out']}f/{r['bytes_out']}B gd={r['gd_calls']} LS={ls} SS={st['session']} "
            f"CK={ {k: v['value'] for k, v in st['cookies'].items()} } dup={ {k: v for k, v in r['var_counts'].items() if v > 1} } "
            f"cons={len(r['console'])} fail={len(r['failed'])} perr={len(r['pageerrors'])}")


res = {}
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROMIUM)

    for path, lab in (("/", "fresh_index"), ("/onload", "fresh_onload"), ("/plainload", "fresh_plainload")):
        ctx = b.new_context()
        t = Tab(ctx, lab)
        res[lab] = t.load(path, lab)
        print(brief(res[lab]), flush=True)
        ctx.close()

    # user sets values, then reloads
    ctx = b.new_context()
    t = Tab(ctx, "user")
    res["user_first"] = t.load("/", "user_first")
    for sel in ("#set-user", "#set-user-sub", "#box-a-choose", "#box-b-choose", "#good-tok"):
        res[f"click{sel}"] = t.click(sel, f"click{sel}")
    res["user_after_clicks"] = t.summarize(t.mark(), "user_after_clicks")
    print(brief(res["user_after_clicks"]), flush=True)
    t.page.wait_for_timeout(3000)
    e1 = {k: v["expires"] for k, v in t.storage()["cookies"].items()}
    res["user_reload1"] = t.reload("user_reload1")
    e2 = {k: v["expires"] for k, v in t.storage()["cookies"].items()}
    res["cookie_slide"] = {"before": e1, "after": e2, "delta_s": {k: round(e2.get(k, 0) - e1.get(k, 0), 1) for k in e1}}
    print(brief(res["user_reload1"]), flush=True)
    print("cookie_slide", res["cookie_slide"]["delta_s"], flush=True)
    res["user_reload2"] = t.reload("user_reload2")
    print(brief(res["user_reload2"]), flush=True)
    res["user_probe"] = t.click("#probe", "user_probe")
    res["user_probe"]["gd_traces"] = res["user_probe"]["gd_traces"]
    # navigation
    for sel, lab in (("#nav-onload", "nav_onload"), ("#nav-plainload", "nav_plainload"), ("#nav-home", "nav_home")):
        m = t.mark()
        t.page.click(sel)
        t.page.wait_for_timeout(1500)
        res[lab] = t.summarize(m, lab)
        print(brief(res[lab]), flush=True)
    # second tab in the same context (shares LS + cookies, own token / sessionStorage)
    t2 = Tab(ctx, "user_tab2")
    res["user_tab2"] = t2.load("/", "user_tab2")
    print(brief(res["user_tab2"]), flush=True)
    ctx.close()

    # bad token sanitised by the get_delta override
    ctx = b.new_context()
    t = Tab(ctx, "badtok")
    t.load("/", "badtok_first")
    t.page.evaluate("() => localStorage.setItem('be_tok', 'bad-xyz')")
    res["bad_tok_reload"] = t.reload("bad_tok_reload")
    print(brief(res["bad_tok_reload"]), flush=True)
    res["bad_tok_reload2"] = t.reload("bad_tok_reload2")
    print(brief(res["bad_tok_reload2"]), flush=True)
    ctx.close()

    # server value (on_load) must win
    ctx = b.new_context()
    t = Tab(ctx, "srv")
    t.load("/", "srv_first")
    t.page.evaluate("() => { localStorage.setItem('be_srv', 'browser-old'); document.cookie = 'be_srv_ck=browser-old; path=/'; }")
    res["server_wins"] = t.load("/onload", "server_wins")
    print(brief(res["server_wins"]), flush=True)
    res["server_wins_reload"] = t.reload("server_wins_reload")
    print(brief(res["server_wins_reload"]), flush=True)
    ctx.close()

    # computed vars over storage right after boot
    ctx = b.new_context()
    t = Tab(ctx, "cv")
    t.load("/", "cv_first")
    t.page.evaluate("() => { localStorage.setItem('be_theme', 'blue'); localStorage.setItem('be_note', 'hello'); localStorage.setItem('be_sub_ls', 'subval'); document.cookie = 'be_ck=c1; path=/'; }")
    m = t.mark()
    t.page.reload()
    early = None
    for _ in range(300):
        try:
            if t.page.inner_text("#hyd-flag", timeout=100) == "H:yes":
                early = {i: t.page.inner_text(f"#{i}", timeout=200) for i in ("theme", "theme-upper", "note-len", "ck-combo", "sub-combo")}
                break
        except Exception:
            pass
        t.page.wait_for_timeout(20)
    t.page.wait_for_timeout(1500)
    res["cv_boot"] = t.summarize(m, "cv_boot")
    res["cv_boot"]["ui_at_first_hydrated"] = early
    print(brief(res["cv_boot"]), "early=", early, flush=True)
    ctx.close()
    b.close()

Path(OUT).write_text(json.dumps(res, indent=1, default=str))
print("wrote", OUT)
