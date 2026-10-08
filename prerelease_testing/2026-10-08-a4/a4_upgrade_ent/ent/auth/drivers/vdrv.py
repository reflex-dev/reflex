"""Verifier driver for the ent_auth A-1 / A-2 claims (independent of the explorer's probes).

Usage (run with the shared Playwright venv, proxy bypass on the client side only):
  NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python vdrv.py \
      xtab  <base_url> <label> <N>          # manual two-tab logout flow, N repetitions
  ... vdrv.py stale <base_url> <label> <N>  # deterministic stale-localStorage-at-boot probe
  ... vdrv.py logins <base_url> <label> <N> # N full logins in fresh contexts; count token cookies (A-2)

Every run writes <outdir>/<label>-<mode>.json (per-repetition records incl. websocket frame
summaries, storage writes/events, console, failed requests, cookie-sync statuses) and prints a
summary line. Screenshots go to <outdir>/../shots/.
"""

import json
import os
import random
import sys
import time
from pathlib import Path

import playwright  # VENV_GUARD

assert "/scratchpad/envs/driver/" in playwright.__file__, playwright.__file__
from playwright.sync_api import sync_playwright

CHROMIUM = "/opt/pw-browsers/chromium"
HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "logs"
SHOTS = HERE.parent / "shots"
HASH_SUFFIX = "latest_access_token_hash_ls_rx_state_"
IDP = "http://localhost:8638"  # a3_ent_auth mock IdP (the a2 verifier used 8738)

INIT_JS = r"""
(() => {
  const rec = (kind, data) => { try { window.vrec({kind, t: Date.now(), url: location.pathname, ...data}); } catch (e) {} };
  const origSet = Storage.prototype.setItem;
  Storage.prototype.setItem = function (k, v) {
    if (this === window.localStorage && String(k).includes('latest_access_token_hash_ls'))
      rec('ls_set', {key: 'hash', value: String(v)});
    return origSet.apply(this, arguments);
  };
  const origRemove = Storage.prototype.removeItem;
  Storage.prototype.removeItem = function (k) {
    if (this === window.localStorage && String(k).includes('latest_access_token_hash_ls'))
      rec('ls_remove', {key: 'hash'});
    return origRemove.apply(this, arguments);
  };
  window.addEventListener('storage', (e) => {
    if (String(e.key).includes('latest_access_token_hash_ls'))
      rec('storage_event', {old: e.oldValue, new: e.newValue});
  });
})();
"""


def short(v, n=16):
    """Shorten a hash-like value for logs."""
    if v is None:
        return None
    v = str(v)
    return v if len(v) <= n else v[:n] + "..."


def parse_sio(payload):
    """Parse a socket.io text frame into (packet_type, data) or None."""
    if not isinstance(payload, str):
        return None
    i = 0
    while i < len(payload) and payload[i].isdigit():
        i += 1
    ptype, rest = payload[:i], payload[i:]
    if rest.startswith("/"):
        # namespaced packet: 42/_event,[...]
        _, _, rest = rest.partition(",")
    if not rest:
        return ptype, None
    try:
        data = json.loads(rest)
    except Exception:
        return ptype, rest[:200]
    return ptype, data


def summarize_delta(delta):
    """Keep the interesting parts of a delta: hash, is_hydrated, auth user, vault."""
    out = {}
    if not isinstance(delta, dict):
        return out
    for sname, sub in delta.items():
        if not isinstance(sub, dict):
            continue
        for k, v in sub.items():
            if "latest_access_token_hash" in k:
                out["hash"] = short(v)
            elif k.startswith("is_hydrated"):
                out["is_hydrated"] = v
            elif "auth_user_state" in sname and k.startswith("sub"):
                out["user_sub"] = v
            elif "vault" in sname and (k.startswith("clicks") or k.startswith("entries")):
                out[k.replace("_rx_state_", "")] = v
            elif "has_any_token" in k:
                out["has_any_token"] = v
    return out


class Tab:
    """A page with websocket/console/network capture."""

    def __init__(self, ctx, name, log):
        self.name = name
        self.log = log
        self.page = ctx.new_page()
        self.page._vname = name
        PUMP["page"] = self.page
        p = self.page
        p.on("websocket", self._on_ws)
        p.on("console", lambda m: self._ev("console", type=m.type, text=m.text[:300]))
        p.on("pageerror", lambda e: self._ev("pageerror", text=str(e)[:300]))
        p.on("requestfailed", lambda r: self._ev("requestfailed", url=r.url[:120], failure=r.failure))
        p.on("response", self._on_resp)
        p.on("framenavigated", lambda f: f == p.main_frame and self._ev("nav", to=f.url))

    def _ev(self, kind, **kw):
        self.log.append({"tab": self.name, "kind": kind, "t": time.time() * 1000, **kw})

    def _on_resp(self, r):
        if "/_reflex/cookies/sync" in r.url:
            self._ev("cookie_sync", status=r.status, pid=r.headers.get("x-worker-pid"))
        elif r.status >= 400:
            self._ev("http_error", status=r.status, url=r.url[:120])

    def _on_ws(self, ws):
        self._ev("ws_open", url=ws.url[:80])
        ws.on("framesent", lambda payload: self._frame("sent", payload))
        ws.on("framereceived", lambda payload: self._frame("recv", payload))
        ws.on("close", lambda w: self._ev("ws_close"))

    def _frame(self, direction, payload):
        parsed = parse_sio(payload)
        if parsed is None:
            return
        ptype, data = parsed
        if ptype in ("2", "3"):  # engine.io ping/pong
            return
        rec = {"dir": direction, "ptype": ptype}
        try:
            if ptype == "40" and isinstance(data, dict) and "event" in data:
                ev = data["event"]
                rec["events"] = [ev.get("name", "").rpartition(".")[2]]
                rec["vars"] = {k.rpartition(".")[2]: short(v) for k, v in ((ev.get("payload") or {}).get("vars") or {}).items()}
            elif ptype == "42" and isinstance(data, list) and data:
                body = data[1] if len(data) > 1 else None
                if isinstance(body, str):
                    try:
                        body = json.loads(body)
                    except Exception:
                        pass
                if direction == "sent" and isinstance(body, dict):
                    rec["events"] = [body.get("name", "").rpartition(".")[2]]
                    pv = (body.get("payload") or {}).get("vars")
                    if pv:
                        rec["vars"] = {k.rpartition(".")[2]: short(v) for k, v in pv.items()}
                elif isinstance(body, dict):
                    rec["delta"] = summarize_delta(body.get("delta"))
                    evs = body.get("events") or []
                    rec["chained"] = [e.get("name", "").rpartition(".")[2] for e in evs if isinstance(e, dict)]
                    if not rec["delta"] and not rec["chained"]:
                        return
            else:
                rec["raw"] = str(payload)[:160]
        except Exception as e:  # never break the run on a parse problem
            rec["parse_error"] = str(e)
        self._ev("ws", **rec)

    def text(self, sel, timeout=3000):
        try:
            return self.page.locator(sel).first.inner_text(timeout=timeout)
        except Exception:
            return None

    def path(self):
        from urllib.parse import urlparse

        return urlparse(self.page.url).path.rstrip("/") or "/"

    def ls_hash(self):
        return self.page.evaluate(
            "() => { for (let i=0;i<localStorage.length;i++){const k=localStorage.key(i); if(k.endsWith('%s')) return localStorage.getItem(k);} return null; }"
            % HASH_SUFFIX
        )

    def set_ls_hash(self, value, key=None):
        return self.page.evaluate(
            "([v, k0]) => { let k=k0; for (let i=0;i<localStorage.length && !k;i++){const kk=localStorage.key(i); if(kk.endsWith('%s')) k=kk;} localStorage.setItem(k, v); return k; }"
            % HASH_SUFFIX,
            [value, key],
        )


PUMP = {"page": None}


def pause(seconds, page=None):
    """Sleep while letting Playwright dispatch events (time.sleep would starve the event loop)."""
    page = page or PUMP["page"]
    try:
        page.wait_for_timeout(seconds * 1000)
    except Exception:
        time.sleep(seconds)


def wait_for(fn, timeout=30.0, interval=0.25, page=None):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        try:
            last = fn()
            if last:
                return last
        except Exception:
            pass
        pause(interval, page)
    return last


def login(tab, base, user="alice"):
    """Log in through the mock IdP starting from the protected page."""
    p = tab.page
    p.goto(base + "/vault")
    wait_for(lambda: tab.path() == "/login", 60)
    p.get_by_role("button", name="Login with Generic").click(timeout=30000)
    p.wait_for_url(IDP + "/oauth2/authorize**", timeout=30000)
    p.fill("#subject-input", user)
    p.get_by_role("button", name="Authorize", exact=True).click()
    ok = wait_for(lambda: tab.path() == "/vault" and tab.text("#who", 500) == user, 60)
    return bool(ok)


def oidc_cookies(ctx):
    return sorted(c["name"] for c in ctx.cookies() if "oidc" in c["name"].lower())


def wait_hydrated(tab, timeout=20):
    """Wait until the page's socket is connected and the boot delta arrived (is_hydrated true)."""
    start = len(tab.log)
    return wait_for(
        lambda: any(
            e.get("tab") == tab.name and e.get("kind") == "ws" and (e.get("delta") or {}).get("is_hydrated") is True
            for e in tab.log[start - 50 if start > 50 else 0 :]
        ),
        timeout,
    )


def new_context(browser, log):
    ctx = browser.new_context(viewport={"width": 1100, "height": 800})

    def vrec(source, rec):
        log.append({"tab": getattr(source["page"], "_vname", "?"), **rec, "t": rec.get("t")})

    ctx.expose_binding("vrec", vrec)
    ctx.add_init_script(INIT_JS)
    return ctx


def boot_events(log, tab, since_idx):
    """Event names this tab SENT after a log index (boot sequence)."""
    names = []
    for e in log[since_idx:]:
        if e.get("tab") == tab and e.get("kind") == "ws" and e.get("dir") == "sent":
            names.extend(e.get("events") or [])
    return names


def run_xtab(browser, base, label, rep):
    """Manual two-tab flow: tab1 logged in on /vault, tab2 logs out, check tab1."""
    log = []
    ctx = new_context(browser, log)
    r = {"rep": rep}
    try:
        t1 = Tab(ctx, "tab1", log)
        r["login"] = login(t1, base)
        wait_for(lambda: t1.ls_hash(), 15)
        pause(1.5)
        r["tab1_hash_after_login"] = short(t1.ls_hash())
        r["cookies_after_login"] = oidc_cookies(ctx)
        t2 = Tab(ctx, "tab2", log)
        t2.page.goto(base + "/vault")
        r["tab2_logged_in"] = bool(wait_for(lambda: t2.text("#who", 500) == "alice", 30))
        pause(2)
        mark_logout = len(log)
        r["t_logout_click"] = time.time() * 1000
        t2.page.click("#logout")
        t2.page.wait_for_url(IDP + "/oauth2/end_session**", timeout=30000)
        idx_before_return = len(log)
        t2.page.get_by_role("button", name="End session").click()
        wait_for(lambda: t2.page.url.startswith(base) and t2.path() == "/", 30)
        wait_for(lambda: t2.text("#who", 500) == "", 20)
        pause(2)
        r["tab2_boot_events"] = boot_events(log, "tab2", idx_before_return)
        pause(6)
        r["tab1_who_before_add"] = t1.text("#who", 1000)
        r["tab1_path_before_add"] = t1.path()
        r["cookies_after_logout"] = oidc_cookies(ctx)
        r["ls_hash_after_logout"] = short(t1.ls_hash())
        clicks0 = t1.text("#clicks", 1000)
        idx_add = len(log)
        if t1.path() == "/vault":
            try:
                t1.page.click("#add", timeout=3000)
            except Exception as e:
                r["add_click_error"] = str(e)[:100]
        pause(3)
        r["tab1_path_after_add"] = t1.path()
        r["tab1_clicks"] = [clicks0, t1.text("#clicks", 1000)]
        r["tab1_entries"] = t1.page.locator(".entry").all_inner_texts() if t1.path() == "/vault" else []
        r["add_response"] = [
            {k: e.get(k) for k in ("dir", "events", "delta", "chained")}
            for e in log[idx_add:]
            if e.get("tab") == "tab1" and e.get("kind") == "ws"
        ][:6]
        t1.page.screenshot(path=str(SHOTS / f"{label}-xtab-{rep}-tab1-after-add.png"))
        idx_reload = len(log)
        t1.page.reload()
        pause(5)
        r["tab1_boot_events_reload"] = boot_events(log, "tab1", idx_reload)
        r["tab1_path_after_reload"] = t1.path()
        r["tab1_who_after_reload"] = t1.text("#who", 2000)
        t1.page.screenshot(path=str(SHOTS / f"{label}-xtab-{rep}-tab1-after-reload.png"))
        # A brand-new tab must be anonymous.
        t3 = Tab(ctx, "tab3", log)
        t3.page.goto(base + "/vault")
        pause(4)
        r["tab3_path"] = t3.path()
        accepted = any(
            "alice" in (e or "") for e in r["tab1_entries"]
        ) and r["tab1_clicks"][1] not in (None, r["tab1_clicks"][0])
        r["tab1_event_accepted"] = accepted
        r["tab1_logged_out"] = (not accepted) and r["tab1_path_after_reload"] == "/login"
        r["timeline"] = [
            {k: v for k, v in e.items() if k not in ("url",)}
            for e in log[mark_logout:]
            if e.get("kind") in ("ls_set", "storage_event", "cookie_sync", "nav")
            or (e.get("kind") == "ws" and (e.get("events") or e.get("delta", {}).get("hash") is not None or e.get("chained")))
        ]
    except Exception as e:
        r["error"] = repr(e)[:300]
    finally:
        r["console_errors"] = [e for e in log if e.get("kind") in ("pageerror",) or (e.get("kind") == "console" and e.get("type") in ("error", "warning"))][:30]
        r["requestfailed"] = [e for e in log if e.get("kind") == "requestfailed"][:20]
        r["http_errors"] = [e for e in log if e.get("kind") == "http_error"][:20]
        r["cookie_sync_statuses"] = [(e["tab"], e["status"], e.get("pid")) for e in log if e.get("kind") == "cookie_sync"]
        r["_full_log"] = log
        ctx.close()
    return r


def run_stale(browser, base, label, rep):
    """Deterministic probes of how a tab reconciles a stale token hash.

    P1 anon boot with a bogus hash in localStorage -> expect backend writes "" back.
    P2 logged-in boot with a bogus hash -> expect backend re-asserts the real hash.
    P3 logged-in tab away from the app while ANOTHER tab clears the cookies and writes hash "" (what a
       completed logout leaves behind); tab returns to /vault -> expect logged out (/login).
    P4 control: same as P3 but tab1 stays on the page and receives the storage event live.
    """
    r = {"rep": rep}
    bogus = "bogus-%06d" % random.randint(0, 999999)
    # P1
    log = []
    ctx = new_context(browser, log)
    try:
        t = Tab(ctx, "p1", log)
        t.page.goto(base + "/")
        wait_hydrated(t)
        pause(1.5)
        key = t.set_ls_hash(bogus, None) if t.ls_hash() is not None else None
        if key is None:
            key = t.page.evaluate(
                "() => Object.keys(localStorage).find(k => k.endsWith('%s')) || null" % HASH_SUFFIX
            )
        if key is None:
            # The key has never been written in this fresh browser: use the compiled name.
            key = "reflex___state____state.reflex_enterprise___auth___oidc___state____generic_oidc_auth_state." + HASH_SUFFIX
            t.set_ls_hash(bogus, key)
        idx = len(log)
        t.page.reload()
        wait_hydrated(t)
        pause(5)
        r["p1_boot_events"] = boot_events(log, "p1", idx)
        r["p1_boot_vars"] = [e.get("vars") for e in log[idx:] if e.get("tab") == "p1" and e.get("kind") == "ws" and e.get("dir") == "sent" and e.get("vars")][:3]
        r["p1_after"] = short(t.ls_hash())
        r["p1_corrected"] = t.ls_hash() == ""
        r["p1_cookie_syncs"] = [e["status"] for e in log[idx:] if e.get("kind") == "cookie_sync"]
    except Exception as e:
        r["p1_error"] = repr(e)[:300]
    finally:
        r["p1_log"] = log
        ctx.close()
    # P2
    log = []
    ctx = new_context(browser, log)
    try:
        t = Tab(ctx, "p2", log)
        r["p2_login"] = login(t, base)
        real = wait_for(lambda: t.ls_hash(), 15)
        pause(1.5)
        real = t.ls_hash()
        r["p2_real"] = short(real)
        t.set_ls_hash(bogus)
        idx = len(log)
        t.page.reload()
        wait_hydrated(t)
        pause(5)
        r["p2_boot_events"] = boot_events(log, "p2", idx)
        r["p2_after"] = short(t.ls_hash())
        r["p2_corrected"] = bool(real) and t.ls_hash() == real
        r["p2_cookie_syncs"] = [e["status"] for e in log[idx:] if e.get("kind") == "cookie_sync"]
    except Exception as e:
        r["p2_error"] = repr(e)[:300]
    finally:
        r["p2_log"] = log
        ctx.close()
    # P3: tab1 away (about:blank keeps its sessionStorage/client token), helper tab simulates the
    # end state of a logout elsewhere: no cookies, hash "".
    log = []
    ctx = new_context(browser, log)
    try:
        t1 = Tab(ctx, "p3tab1", log)
        r["p3_login"] = login(t1, base)
        wait_for(lambda: t1.ls_hash(), 15)
        pause(1.5)
        t1.page.goto("about:blank")
        helper = Tab(ctx, "p3helper", log)
        helper.page.goto(base + "/pid")
        wait_hydrated(helper)
        ctx.clear_cookies()
        helper.set_ls_hash("")
        helper.page.close()
        PUMP["page"] = t1.page
        r["p3_cookies_before_return"] = oidc_cookies(ctx)
        idx = len(log)
        t1.page.goto(base + "/vault")
        pause(6)
        r["p3_boot_events"] = boot_events(log, "p3tab1", idx)
        r["p3_path"] = t1.path()
        r["p3_who"] = t1.text("#who", 1500)
        if t1.path() == "/vault":
            c0 = t1.text("#clicks", 1000)
            t1.page.click("#add")
            pause(3)
            r["p3_add"] = [c0, t1.text("#clicks", 1000), t1.page.locator(".entry").all_inner_texts()]
            r["p3_path_after_add"] = t1.path()
        r["p3_logged_out"] = r["p3_path"] == "/login" or r.get("p3_path_after_add") == "/login"
        t1.page.screenshot(path=str(SHOTS / f"{label}-stale-{rep}-p3.png"))
    except Exception as e:
        r["p3_error"] = repr(e)[:300]
    finally:
        r["p3_log"] = log
        ctx.close()
    # P4 control: same end state delivered live via the storage event.
    log = []
    ctx = new_context(browser, log)
    try:
        t1 = Tab(ctx, "p4tab1", log)
        r["p4_login"] = login(t1, base)
        wait_for(lambda: t1.ls_hash(), 15)
        pause(1.5)
        helper = Tab(ctx, "p4helper", log)
        helper.page.goto(base + "/pid")
        wait_hydrated(helper)
        ctx.clear_cookies()
        idx = len(log)
        helper.set_ls_hash("")
        pause(6)
        r["p4_tab1_sent"] = boot_events(log, "p4tab1", idx)
        r["p4_path"] = t1.path()
        r["p4_who"] = t1.text("#who", 1500)
        if t1.path() == "/vault":
            c0 = t1.text("#clicks", 1000)
            try:
                t1.page.click("#add", timeout=3000)
            except Exception:
                pass
            pause(3)
            r["p4_add"] = [c0, t1.text("#clicks", 1000)]
            r["p4_path_after_add"] = t1.path()
        r["p4_logged_out"] = r["p4_path"] == "/login" or r.get("p4_path_after_add") == "/login" or r["p4_who"] == ""
    except Exception as e:
        r["p4_error"] = repr(e)[:300]
    finally:
        r["p4_log"] = log
        ctx.close()
    return r


def run_login(browser, base, label, rep):
    """A full login in a fresh context; record cookie-sync statuses/pids and resulting cookies."""
    log = []
    ctx = new_context(browser, log)
    r = {"rep": rep}
    try:
        t = Tab(ctx, "login", log)
        r["login"] = login(t, base)
        pause(4)
        r["cookies"] = oidc_cookies(ctx)
        r["ls_hash"] = short(t.ls_hash())
        r["cookie_syncs"] = [(e["status"], e.get("pid")) for e in log if e.get("kind") == "cookie_sync"]
        t2 = Tab(ctx, "newtab", log)
        t2.page.goto(base + "/vault")
        pause(5)
        r["newtab_path"] = t2.path()
        r["newtab_who"] = t2.text("#who", 1500)
    except Exception as e:
        r["error"] = repr(e)[:300]
    finally:
        r["console_errors"] = [e for e in log if e.get("kind") == "pageerror" or (e.get("kind") == "console" and e.get("type") == "error")][:20]
        r["_full_log"] = log
        ctx.close()
    return r


def run_logout_cookies(browser, base, label, rep, max_attempts=8):
    """A-2 security variant: once a login DID store token cookies, log out; are they cleared?"""
    r = {"rep": rep, "attempts": 0}
    for attempt in range(max_attempts):
        log = []
        ctx = new_context(browser, log)
        try:
            t = Tab(ctx, "lo", log)
            r["attempts"] = attempt + 1
            if not login(t, base):
                continue
            pause(3)
            if not oidc_cookies(ctx):
                continue
            r["cookies_before_logout"] = oidc_cookies(ctx)
            idx = len(log)
            t.page.click("#logout")
            t.page.wait_for_url(IDP + "/oauth2/end_session**", timeout=30000)
            t.page.get_by_role("button", name="End session").click()
            wait_for(lambda: t.page.url.startswith(base) and t.path() == "/", 30)
            pause(4)
            r["logout_cookie_syncs"] = [(e["status"], e.get("pid")) for e in log[idx:] if e.get("kind") == "cookie_sync"]
            r["cookies_after_logout"] = oidc_cookies(ctx)
            t2 = Tab(ctx, "newtab", log)
            t2.page.goto(base + "/vault")
            pause(5)
            r["newtab_path"] = t2.path()
            r["newtab_who"] = t2.text("#who", 1500)
            r["_full_log"] = log
            return r
        except Exception as e:
            r["error"] = repr(e)[:300]
        finally:
            ctx.close()
    return r


def run_away(browser, base, label, rep):
    """Realistic deterministic form: tab1 (alice, /vault) follows a link to another site; the user
    logs out normally in tab2 (real UI + IdP end_session); tab1 presses Back. Is tab1 signed out?"""
    log = []
    ctx = new_context(browser, log)
    r = {"rep": rep}
    try:
        t1 = Tab(ctx, "tab1", log)
        r["login"] = login(t1, base)
        wait_for(lambda: t1.ls_hash(), 15)
        pause(1.5)
        t1.page.goto(IDP + "/")  # another origin: the app page is gone, no storage events reach it
        t2 = Tab(ctx, "tab2", log)
        t2.page.goto(base + "/vault")
        r["tab2_logged_in"] = bool(wait_for(lambda: t2.text("#who", 500) == "alice", 30))
        pause(1.5)
        t2.page.click("#logout")
        t2.page.wait_for_url(IDP + "/oauth2/end_session**", timeout=30000)
        t2.page.get_by_role("button", name="End session").click()
        wait_for(lambda: t2.page.url.startswith(base) and t2.path() == "/", 30)
        pause(3)
        r["cookies_after_logout"] = oidc_cookies(ctx)
        r["ls_hash_after_logout"] = short(t2.ls_hash())
        t2.page.close()
        PUMP["page"] = t1.page
        idx = len(log)
        t1.page.go_back()
        pause(6)
        r["tab1_back_url"] = t1.page.url
        r["tab1_boot_events"] = boot_events(log, "tab1", idx)
        r["tab1_who"] = t1.text("#who", 1500)
        if t1.path() == "/vault":
            c0 = t1.text("#clicks", 1000)
            try:
                t1.page.click("#add", timeout=3000)
            except Exception:
                pass
            pause(3)
            r["tab1_add"] = [c0, t1.text("#clicks", 1000), t1.page.locator(".entry").all_inner_texts() if t1.path() == "/vault" else []]
        r["tab1_path_final"] = t1.path()
        r["tab1_logged_out"] = r["tab1_path_final"] == "/login"
        t1.page.screenshot(path=str(SHOTS / f"{label}-away-{rep}-tab1.png"))
    except Exception as e:
        r["error"] = repr(e)[:300]
    finally:
        r["_full_log"] = log
        ctx.close()
    return r


def run_storm(browser, base, label, rep, max_attempts=6, window=40):
    """A-2 side effect: after a login whose cookie sync got 405 (no token cookies), open a second
    tab and count cookie-sync POSTs / websocket events per 5 s for `window` seconds."""
    r = {"rep": rep}
    for attempt in range(max_attempts):
        log = []
        ctx = new_context(browser, log)
        try:
            t = Tab(ctx, "login", log)
            r["attempts"] = attempt + 1
            if not login(t, base):
                continue
            pause(3)
            if oidc_cookies(ctx):
                continue  # sync succeeded; we want the failed-sync case
            r["login_syncs"] = [(e["status"], e.get("pid")) for e in log if e.get("kind") == "cookie_sync"]
            t2 = Tab(ctx, "newtab", log)
            t0 = time.time() * 1000
            t2.page.goto(base + "/vault")
            pause(window)
            buckets = {}
            for e in log:
                if (e.get("t") or 0) < t0:
                    continue
                b = int((e["t"] - t0) // 5000) * 5
                if e.get("kind") == "cookie_sync":
                    buckets.setdefault(b, [0, 0])[0] += 1
                elif e.get("kind") == "ws" and e.get("dir") == "sent":
                    buckets.setdefault(b, [0, 0])[1] += 1
            r["per_5s_[syncs,ws_events]"] = {f"{k}-{k + 5}s": v for k, v in sorted(buckets.items())}
            r["newtab_path"] = t2.path()
            r["login_tab_who"] = t.text("#who", 1000)
            return r
        except Exception as e:
            r["error"] = repr(e)[:300]
        finally:
            ctx.close()
    return r


def main():
    mode, base, label, n = sys.argv[1], sys.argv[2].rstrip("/"), sys.argv[3], int(sys.argv[4])
    OUT.mkdir(exist_ok=True)
    SHOTS.mkdir(exist_ok=True)
    fn = {"xtab": run_xtab, "stale": run_stale, "logins": run_login, "logoutcookies": run_logout_cookies, "away": run_away, "storm": run_storm}[mode]
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        try:
            for rep in range(n):
                res = fn(browser, base, label, rep)
                results.append(res)
                brief = {k: v for k, v in res.items() if not k.endswith("_log") and k not in ("timeline", "add_response", "console_errors", "requestfailed", "http_errors")}
                print(json.dumps(brief, default=str), flush=True)
        finally:
            browser.close()
    out = OUT / f"{label}-{mode}.json"
    out.write_text(json.dumps(results, indent=1, default=str))
    if mode == "xtab":
        lo = sum(1 for r in results if r.get("tab1_logged_out"))
        print(f"SUMMARY {label} xtab: tab1 logged out {lo}/{len(results)}; accepted-after-logout {sum(1 for r in results if r.get('tab1_event_accepted'))}/{len(results)}")
    elif mode == "stale":
        s = {k: sum(1 for r in results if r.get(k)) for k in ("p1_corrected", "p2_corrected", "p3_logged_out", "p4_logged_out")}
        print(f"SUMMARY {label} stale: {json.dumps(s)} of {len(results)}")
    elif mode == "storm":
        print(f"SUMMARY {label} storm: see per-5s counts above")
    elif mode == "away":
        lo = sum(1 for r in results if r.get("tab1_logged_out"))
        print(f"SUMMARY {label} away: tab1 logged out after Back {lo}/{len(results)}")
    elif mode == "logoutcookies":
        left = sum(1 for r in results if r.get("cookies_after_logout"))
        relog = sum(1 for r in results if r.get("newtab_who") == "alice")
        print(f"SUMMARY {label} logoutcookies: cookies left after logout {left}/{len(results)}; new tab signed in as alice after logout {relog}/{len(results)}")
    else:
        ok = sum(1 for r in results if r.get("cookies"))
        print(f"SUMMARY {label} logins: with token cookies {ok}/{len(results)}")
    print("wrote", out)


if __name__ == "__main__":
    main()
