"""reflex#7360 enterprise router probe on the vauthd app (deep links, client nav, logout, cookie exposure).

Usage:
  NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python deeplink.py <base_url> <label> [reps]

Checks per repetition (fresh browser context each):
  A deep_query      anonymous full load of /vault?x=1&y=two%20words -> /login?redirect_to=<same> -> login -> back on the same URL,
                    on_load sees the query, server-side cookie header has the OIDC cookies, protected event attributed to alice.
  B deep_dynamic    anonymous full load of /item/abc?z=9 -> login -> back on /item/abc?z=9, on_load params {"item": "abc"}.
  C nav_anon        anonymous on /, client-side link to /vault?x=nav -> redirect_to carries /vault?x=nav (NOT /), login -> /vault?x=nav.
  D nav_auth        signed in: client nav / -> /vault2?q=5&r=a%20b -> /item/xyz?k=1 -> /vault?x=nav; every on_load sees its own page.
  E reload          signed in: reload /item/xyz?k=1 keeps the page and on_load sees it.
  F logout          signed in on /vault: click logout -> where it lands, cookies cleared, /vault again -> /login?redirect_to=%2Fvault.
  G fe_exposure     public page: rendered State.router.headers.cookie, raw_headers keys, and every received websocket frame
                    scanned for cookie names / "cookie" / "authorization" keys.
Writes ../logs/<label>-deeplink.json; prints one JSON line per scenario and a SUMMARY line.
"""

import json
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import playwright  # VENV_GUARD

assert ("/envs/" + __import__("os").environ.get("DRV_VENV", "driver") + "/") in playwright.__file__, playwright.__file__
from playwright.sync_api import sync_playwright

CHROMIUM = "/opt/pw-browsers/chromium"
HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "logs"
SHOTS = HERE.parent / "shots"
IDP = "http://localhost:8638"
PUMP = {}
SEEN_COOKIE_VALUES = {}  # value -> (name, httpOnly)


class Tab:
    def __init__(self, ctx, name, log):
        self.name, self.log = name, log
        self.page = p = ctx.new_page()
        PUMP["page"] = p
        self.frames_recv = []
        self.navs = []
        p.on("console", lambda m: m.type in ("error", "warning") and self.log.append({"tab": name, "kind": "console", "type": m.type, "text": m.text[:300]}))
        p.on("pageerror", lambda e: self.log.append({"tab": name, "kind": "pageerror", "text": str(e)[:300]}))
        p.on("requestfailed", lambda r: self.log.append({"tab": name, "kind": "requestfailed", "url": r.url[:140], "failure": r.failure}))
        p.on("response", lambda r: r.status >= 400 and self.log.append({"tab": name, "kind": "http_error", "status": r.status, "url": r.url[:140]}))
        p.on("framenavigated", lambda f: f == p.main_frame and self.navs.append(f.url))
        p.on("websocket", lambda ws: ws.on("framereceived", lambda payload: self.frames_recv.append(payload if isinstance(payload, str) else "")))

    def text(self, sel, timeout=3000):
        try:
            return self.page.locator(sel).first.inner_text(timeout=timeout)
        except Exception:
            return None

    def url(self):
        return self.page.url

    def path(self):
        return norm(urlparse(self.page.url).path)


def norm(path):
    """Path without a trailing slash (prod static serving redirects /vault -> /vault/)."""
    return (path or "").rstrip("/") or "/"


def norm_target(target):
    """A redirect_to target (path?query) with the path normalized."""
    if target is None:
        return None
    u = urlparse(target)
    return norm(u.path) + (f"?{u.query}" if u.query else "")


def wait_for(fn, timeout=30.0, interval=0.25):
    """Poll fn() until truthy; pumps Playwright's event loop between polls (time.sleep would starve it)."""
    end = time.time() + timeout
    while time.time() < end:
        try:
            v = fn()
            if v:
                return v
        except Exception:
            pass
        PUMP["page"].wait_for_timeout(int(interval * 1000))
    return None


def pause(t, seconds):
    t.page.wait_for_timeout(int(seconds * 1000))


def do_idp_login(tab, user="alice"):
    """From /login: click the provider button and authorize at the mock IdP."""
    p = tab.page
    p.get_by_role("button", name="Login with Generic").click(timeout=30000)
    p.wait_for_url(IDP + "/oauth2/authorize**", timeout=30000)
    p.fill("#subject-input", user)
    p.get_by_role("button", name="Authorize", exact=True).click()


def login_redirect(tab):
    """Wait for /login and return the decoded redirect_to (or None)."""
    if not wait_for(lambda: tab.path() == "/login", 40):
        return {"at_login": False, "url": tab.url()}
    q = parse_qs(urlparse(tab.url()).query)
    return {"at_login": True, "login_url": tab.url(), "redirect_to": (q.get("redirect_to") or [None])[0]}


def diag(tab):
    keys = ["who", "n_loads", "d_url", "d_path", "d_query", "d_params", "d_cookies", "d_rawck", "d_tok", "d_sid", "d_host", "d_log", "clicks"]
    return {k: tab.text("#" + k, 1500) for k in keys}


def oidc_cookie_names(ctx):
    return sorted(c["name"] for c in ctx.cookies() if "oidc" in c["name"].lower())


def remember_cookies(ctx):
    for c in ctx.cookies():
        if len(c.get("value", "")) >= 12:
            SEEN_COOKIE_VALUES[c["value"]] = (c["name"], bool(c.get("httpOnly")))


CRED_KEYS = ("cookie", "authorization", "proxy-authorization", "cf-access-jwt-assertion", "x-auth-request-access-token",
             "x-forwarded-access-token", "x-amzn-oidc-accesstoken", "x-amzn-oidc-data", "x-goog-iap-jwt-assertion")


def _headers_span(f):
    """(start, end) of the rx_router_headers JSON object in a frame, or None."""
    i = f.find("rx_router_headers")
    if i < 0:
        return None
    j = f.find("{", i)
    depth = 0
    for k in range(j, len(f)):
        if f[k] == "{":
            depth += 1
        elif f[k] == "}":
            depth -= 1
            if depth == 0:
                return (j, k + 1)
    return (j, len(f))


def leak_scan(frames, ctx):
    """Received websocket frames carrying credentials.

    kind "router_headers": a cookie/credential header key, or a cookie value, INSIDE the rx_router_headers object (#7360's claim).
    kind "elsewhere": a cookie value elsewhere in the frame (e.g. enterprise's cookie-sync script, the IdP logout redirect's
    id_token_hint) -- recorded, judged separately.
    """
    remember_cookies(ctx)
    hits = []
    for f in frames:
        span = _headers_span(f)
        seg = f[span[0]:span[1]].lower() if span else ""
        why = []
        for k in CRED_KEYS:
            if f'"{k}":' in seg or f'"{k.replace("-", "_")}":' in seg:
                why.append(f"router_headers key {k}")
        where = []
        for v, (name, httponly) in SEEN_COOKIE_VALUES.items():
            j = f.find(v)
            if j >= 0:
                inside = bool(span) and span[0] <= j < span[1]
                why.append(f"{'router_headers' if inside else 'elsewhere'} VALUE {name} httpOnly={httponly}")
                where.append(f[max(0, j - 160):j] + "<VALUE>")
        if why:
            kind = "router_headers" if any(w.startswith("router_headers") for w in why) else "elsewhere"
            hits.append({"kind": kind, "why": sorted(set(why)), "where": where[:3], "frame": f[:300]})
    return hits


def router_frames(frames):
    """The received frames that set the frontend router url/headers (for the record)."""
    return [f[:2500] for f in frames if "rx_router_url" in f or "rx_router_headers" in f][:12]


def scen_deep(browser, base, path_qs, expect_path, expect_query, expect_params, log):
    ctx = browser.new_context()
    t = Tab(ctx, "deep", log)
    r = {"start": path_qs}
    try:
        t.page.goto(base + path_qs)
        r.update(login_redirect(t))
        # redirect_to is quote()d once by login_url_for; parse_qs decodes it once -> the page URL as the guard saw it
        r["redirect_to_ok"] = norm_target(r.get("redirect_to")) in (path_qs, unquote(path_qs))
        if r.get("at_login"):
            do_idp_login(t)
            r["back"] = bool(wait_for(lambda: t.path() == expect_path and t.text("#who", 500) == "alice", 60))
            r["final_url"] = t.url()
            remember_cookies(ctx)
            wait_for(lambda: (t.text("#n_loads", 500) or "0") != "0", 15)
            pause(t, 1.0)
            d = diag(t)
            r["diag"] = d
            fq = urlparse(t.url()).query
            r["final_query_ok"] = parse_qs(fq) == {k: [v] for k, v in expect_query.items()}
            r["onload_query_ok"] = d["d_query"] == json.dumps(expect_query, sort_keys=True)
            r["onload_path_ok"] = norm(d["d_path"]) == expect_path
            r["onload_params_ok"] = expect_params is None or d["d_params"] == json.dumps({**expect_query, **expect_params}, sort_keys=True)
            r["server_sees_oidc_cookies"] = "_oidc_" in (d["d_cookies"] or "")
            r["origin_ok"] = d["d_host"] == base and norm(urlparse(d["d_url"] or "").path) == expect_path and (d["d_url"] or "").startswith(base + "/") and d["d_tok"] == "True" and d["d_sid"] == "True"
            t.page.click("#add")
            r["entry"] = wait_for(lambda: t.text(".entry", 500), 10)
            r["entry_ok"] = (r["entry"] or "").startswith("click1:alice@" + expect_path)
        r["ok"] = all(r.get(k) for k in ("at_login", "redirect_to_ok", "back", "final_query_ok", "onload_query_ok", "onload_path_ok", "onload_params_ok", "origin_ok", "entry_ok"))
        t.page.screenshot(path=str(SHOTS / f"{LABEL}-deep{expect_path.replace('/', '_')}-{REP}.png"))
    except Exception as e:
        r["exception"] = f"{type(e).__name__}: {str(e)[:300]}"
        r["exception_url"] = t.page.url
    finally:
        r["leaks"] = leak_scan(t.frames_recv, ctx)[:12]
        r["router_frames"] = router_frames(t.frames_recv)
        ctx.close()
    return r


def scen_nav_anon_then_auth(browser, base, log):
    ctx = browser.new_context()
    t = Tab(ctx, "nav", log)
    r = {}
    try:
        t.page.goto(base + "/")
        wait_for(lambda: t.text("#fe_url", 500), 20)
        pause(t, 1.0)
        # G: frontend exposure on the public page (anonymous: no oidc cookies yet, but other cookies may exist)
        r["G_anon_fe_cookie"] = t.text("#fe_cookie")
        r["G_anon_fe_raw_keys"] = t.text("#fe_raw_keys")
        # C: anonymous client-side nav to a protected page with a query string
        t.page.click("#nav-vault")
        lr = login_redirect(t)
        r["C_redirect"] = lr
        r["C_redirect_to_ok"] = norm_target(lr.get("redirect_to")) == "/vault?x=nav"
        r["C_navs"] = t.navs[-4:]
        if lr.get("at_login"):
            do_idp_login(t)
            r["C_back"] = bool(wait_for(lambda: t.path() == "/vault" and t.text("#who", 500) == "alice", 60))
            r["C_final_url"] = t.url()
            remember_cookies(ctx)
            wait_for(lambda: (t.text("#n_loads", 500) or "0") != "0", 15)
            pause(t, 0.8)
            r["C_diag"] = diag(t)
            r["C_ok"] = bool(r["C_redirect_to_ok"] and r["C_back"] and urlparse(t.url()).query == "x=nav" and r["C_diag"]["d_query"] == '{"x": "nav"}')
        # D: signed-in client nav chain
        steps = []
        for sel, ep, eq, epar in (("#nav-home", "/", None, None),
                                  ("#nav-vault2", "/vault2", {"q": "5", "r": "a b"}, {}),
                                  ("#nav-item", "/item/xyz", {"k": "1"}, {"item": "xyz"}),
                                  ("#nav-vault", "/vault", {"x": "nav"}, {})):
            before = t.text("#n_loads", 500) if ep != "/" else None
            t.page.click(sel)
            ok_path = wait_for(lambda: t.path() == ep, 20)
            if ep == "/":
                wait_for(lambda: t.text("#fe_url", 500), 10)
                pause(t, 0.8)
                steps.append({"to": ep, "path_ok": bool(ok_path), "fe_cookie": t.text("#fe_cookie"), "fe_raw_keys": t.text("#fe_raw_keys"), "who": t.text("#who")})
                # click probe: a non-on_load event's server-side view
                t.page.click("#probe")
                wait_for(lambda: t.text("#click_url", 500), 10)
                steps[-1]["click_url"] = t.text("#click_url")
                steps[-1]["click_cookies_has_oidc"] = "_oidc_" in (t.text("#click_cookies") or "")
                continue
            wait_for(lambda: norm(t.text("#d_path", 500)) == ep, 15)
            pause(t, 0.8)
            d = diag(t)
            steps.append({"to": ep, "path_ok": bool(ok_path), "url": t.url(), "diag": d, "n_loads_before": before,
                          "onload_ok": d["d_host"] == base and d["d_url"].startswith(base + "/") and norm(urlparse(d["d_url"]).path) == ep and d["d_tok"] == "True" and norm(d["d_path"]) == ep and d["d_query"] == json.dumps(eq, sort_keys=True) and d["d_params"] == json.dumps({**eq, **epar}, sort_keys=True),
                          "server_sees_oidc_cookies": "_oidc_" in (d["d_cookies"] or "")})
        r["D_steps"] = steps
        r["D_ok"] = all(s["path_ok"] for s in steps) and all(s.get("onload_ok", True) for s in steps)
        # E: reload a dynamic page with query
        t.page.goto(base + "/item/xyz?k=1")
        wait_for(lambda: t.text("#d_path", 500) == "/item/xyz", 20)
        pause(t, 0.8)
        t.page.reload()
        wait_for(lambda: t.text("#who", 500) == "alice", 20)
        wait_for(lambda: t.text("#d_path", 500) == "/item/xyz", 20)
        pause(t, 0.8)
        d = diag(t)
        r["E_diag"] = d
        r["E_server_sees_oidc_cookies_after_reload"] = "_oidc_" in (d["d_cookies"] or "")
        r["E_ok"] = r["E_server_sees_oidc_cookies_after_reload"] and t.path() == "/item/xyz" and d["d_params"] == '{"item": "xyz", "k": "1"}' and d["d_query"] == '{"k": "1"}'
        # F: logout from a protected page
        t.page.goto(base + "/vault")
        wait_for(lambda: t.text("#who", 500) == "alice", 20)
        r["F_cookies_before"] = oidc_cookie_names(ctx)
        remember_cookies(ctx)
        n0 = len(t.navs)
        t.page.click("#logout")
        wait_for(lambda: t.path() != "/vault" or t.text("#who", 300) == "", 20)
        pause(t, 2.0)
        r["F_after_logout_url"] = t.url()
        r["F_navs"] = t.navs[n0:]
        r["F_cookies_after"] = oidc_cookie_names(ctx)
        t.page.goto(base + "/vault")
        lr = login_redirect(t)
        r["F_revisit"] = lr
        r["F_ok"] = r["F_cookies_after"] == [] and lr.get("at_login") and norm_target(lr.get("redirect_to")) == "/vault"
        t.page.screenshot(path=str(SHOTS / f"{LABEL}-logout-{REP}.png"))
    except Exception as e:
        r["exception"] = f"{type(e).__name__}: {str(e)[:300]}"
        r["exception_url"] = t.page.url
    finally:
        r["G_leaks"] = leak_scan(t.frames_recv, ctx)[:12]
        r["router_frames"] = router_frames(t.frames_recv)
        r["G_ok"] = not [h for h in r["G_leaks"] if h["kind"] == "router_headers"] and all((s.get("fe_cookie") in (None, "")) for s in r.get("D_steps", []) if s["to"] == "/")
        ctx.close()
    return r


def main():
    global LABEL, REP
    base, LABEL = sys.argv[1], sys.argv[2]
    reps = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    OUT.mkdir(exist_ok=True)
    SHOTS.mkdir(exist_ok=True)
    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=CHROMIUM)
        for REP in range(1, reps + 1):
            log = []
            rec = {"rep": REP}
            for key, fn in (("A", lambda: scen_deep(browser, base, "/vault?x=1&y=two%20words", "/vault", {"x": "1", "y": "two words"}, {}, log)),
                            ("B", lambda: scen_deep(browser, base, "/item/abc?z=9", "/item/abc", {"z": "9"}, {"item": "abc"}, log)),
                            ("CDEFG", lambda: scen_nav_anon_then_auth(browser, base, log))):
                try:
                    rec[key] = fn()
                except Exception as e:  # keep going; the error is part of the record
                    rec[key] = {"exception": f"{type(e).__name__}: {str(e)[:300]}"}
            rec["events"] = log
            results.append(rec)
            c = rec["CDEFG"]
            print(json.dumps({"rep": REP, "A_ok": rec["A"].get("ok"), "A_redirect_to": rec["A"].get("redirect_to"), "A_final": rec["A"].get("final_url"),
                              "B_ok": rec["B"].get("ok"), "B_redirect_to": rec["B"].get("redirect_to"), "B_final": rec["B"].get("final_url"),
                              "C_ok": c.get("C_ok"), "C_redirect_to": (c.get("C_redirect") or {}).get("redirect_to"), "D_ok": c.get("D_ok"),
                              "E_ok": c.get("E_ok"), "F_ok": c.get("F_ok"), "F_after_logout_url": c.get("F_after_logout_url"),
                              "G_ok": c.get("G_ok"), "G_router_header_leaks": sum(1 for x in (c.get("G_leaks") or []) + (rec["A"].get("leaks") or []) + (rec["B"].get("leaks") or []) if x["kind"] == "router_headers"),
                              "G_other_value_frames": sum(1 for x in (c.get("G_leaks") or []) + (rec["A"].get("leaks") or []) + (rec["B"].get("leaks") or []) if x["kind"] == "elsewhere"),
                              "exceptions": [x.get("exception") for x in (rec["A"], rec["B"], c) if x.get("exception")],
                              "pageerrors": sum(1 for e in log if e["kind"] == "pageerror"),
                              "console_err": sum(1 for e in log if e["kind"] == "console" and e["type"] == "error")}))
        browser.close()
    (OUT / f"{LABEL}-deeplink.json").write_text(json.dumps(results, indent=1, default=str))
    keys = {"A": lambda r: r["A"].get("ok"), "B": lambda r: r["B"].get("ok")}
    for k in "CDEFG":
        keys[k] = (lambda kk: lambda r: r["CDEFG"].get(f"{kk}_ok"))(k)
    tally = {k: sum(1 for r in results if f(r)) for k, f in keys.items()}
    print(f"SUMMARY {LABEL} deeplink: {json.dumps(tally)} of {len(results)}")


if __name__ == "__main__":
    main()
