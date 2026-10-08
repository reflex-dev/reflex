"""#7493 regression hunt on the vauth app (reuses vdrv.py's capture: websocket frames, hash writes, cookie syncs).

Usage (driver venv, client-side proxy bypass):
  hunt.py fresh   <base> <label> <N>  # fresh anonymous browser: every localStorage/sessionStorage/cookie write,
                                      # cookie-sync POSTs and sent events over /, reload, client nav to /vault (->/login),
                                      # /pid, direct /vault. Expect no token-hash / cookie / default written.
  hunt.py loads   <base> <label> <N>  # signed-in browser: per page load (reload x3, new tab /vault, new tab /, client nav,
                                      # 10 s idle with 3 tabs) count cookie-sync POSTs, update_vars_internal /
                                      # reconcile_tokens_after_sync / hydrate_and_load sends, hash writes, storage events.
  hunt.py relogin <base> <label> <N>  # alice: add, reload, logout (IdP end_session), bob logs in on the same tab:
                                      # who=bob, no alice entries, reload keeps bob, protected add attributed to bob.
Writes ../logs/<label>-<mode>.json and prints one JSON line per repetition plus a SUMMARY line.
"""

import collections
import json
import sys
import time

import playwright  # VENV_GUARD

assert "/scratchpad/envs/driver/" in playwright.__file__, playwright.__file__
from playwright.sync_api import sync_playwright

import vdrv
from vdrv import CHROMIUM, IDP, OUT, SHOTS, Tab, login, new_context, oidc_cookies, pause, short, wait_for, wait_hydrated

ALL_WRITES_JS = r"""
(() => {
  const rec = (kind, data) => { try { window.vrec({kind, t: Date.now(), url: location.pathname, ...data}); } catch (e) {} };
  const set = Storage.prototype.setItem, rm = Storage.prototype.removeItem;
  Storage.prototype.setItem = function (k, v) {
    rec('w_set', {store: this === window.localStorage ? 'ls' : 'ss', key: String(k), value: String(v).slice(0, 40)});
    return set.apply(this, arguments);
  };
  Storage.prototype.removeItem = function (k) {
    rec('w_rm', {store: this === window.localStorage ? 'ls' : 'ss', key: String(k)});
    return rm.apply(this, arguments);
  };
  const d = Object.getOwnPropertyDescriptor(Document.prototype, 'cookie');
  Object.defineProperty(document, 'cookie', {
    get() { return d.get.call(document); },
    set(v) { rec('w_cookie', {key: String(v).split('=')[0], value: String(v).slice(0, 80)}); return d.set.call(document, v); },
    configurable: true,
  });
})();
"""


def ctx_with_writes(browser, log):
    ctx = new_context(browser, log)
    ctx.add_init_script(ALL_WRITES_JS)
    return ctx


def counts(log, since, tabs=None):
    """Count the interesting events after a log index."""
    c = collections.Counter()
    for e in log[since:]:
        if tabs and e.get("tab") not in tabs:
            continue
        k = e.get("kind")
        if k == "cookie_sync":
            c[f"cookie_sync_{e.get('status')}"] += 1
        elif k == "ws" and e.get("dir") == "sent":
            for n in e.get("events") or []:
                c["sent:" + n] += 1
        elif k == "ls_set":
            c["hash_write"] += 1
        elif k == "storage_event":
            c["storage_event"] += 1
        elif k == "pageerror" or (k == "console" and e.get("type") == "error" and "TUNNEL" not in (e.get("text") or "")):
            c["console_error"] += 1
    return dict(sorted(c.items()))


def run_fresh(browser, base, label, rep):
    log = []
    ctx = ctx_with_writes(browser, log)
    r = {"rep": rep, "steps": {}}
    try:
        t = Tab(ctx, "fresh", log)
        steps = [
            ("goto /", lambda: t.page.goto(base + "/")),
            ("reload /", lambda: t.page.reload()),
            ("client nav to /vault", lambda: t.page.click("#to-vault")),
            ("goto /pid", lambda: t.page.goto(base + "/pid")),
            ("goto /vault", lambda: t.page.goto(base + "/vault")),
        ]
        for name, act in steps:
            i = len(log)
            act()
            wait_hydrated(t, 6)
            pause(3)
            r["steps"][name] = {"path": t.path(), **counts(log, i)}
        r["writes"] = [
            {k: e.get(k) for k in ("kind", "store", "key", "value", "url")}
            for e in log
            if e.get("kind") in ("w_set", "w_rm", "w_cookie")
        ]
        r["hash_writes"] = [e.get("value") for e in log if e.get("kind") == "ls_set"]
        r["localStorage"] = t.page.evaluate("() => Object.fromEntries(Object.entries(localStorage).map(([k, v]) => [k, String(v).slice(0, 40)]))")
        r["context_cookies"] = sorted(c["name"] for c in ctx.cookies())
        r["document_cookie"] = t.page.evaluate("() => document.cookie")
        r["totals"] = counts(log, 0)
    except Exception as e:
        r["error"] = repr(e)[:300]
    finally:
        r["_full_log"] = log
        ctx.close()
    return r


def run_loads(browser, base, label, rep):
    log = []
    ctx = new_context(browser, log)
    r = {"rep": rep, "steps": {}}
    try:
        t1 = Tab(ctx, "tab1", log)
        r["login"] = login(t1, base)
        wait_for(lambda: t1.ls_hash(), 15)
        pause(3)
        r["hash"] = short(t1.ls_hash())
        r["cookies"] = oidc_cookies(ctx)
        tabs = {"tab1": t1}

        def step(name, act, wait=4):
            i = len(log)
            act()
            pause(wait)
            r["steps"][name] = {
                **counts(log, i),
                **{f"{n}_who": tb.text("#who", 800) for n, tb in tabs.items()},
                **{f"{n}_path": tb.path() for n, tb in tabs.items()},
            }

        for k in range(3):
            step(f"tab1 reload {k}", lambda: t1.page.reload())

        def open_tab(name, path):
            tb = Tab(ctx, name, log)
            tabs[name] = tb
            tb.page.goto(base + path)

        step("tab2 open /vault", lambda: open_tab("tab2", "/vault"))
        step("tab3 open /", lambda: open_tab("tab3", "/"))
        step("tab3 client nav to /vault", lambda: tabs["tab3"].page.click("#to-vault"))
        step("idle 10 s (3 tabs)", lambda: None, wait=10)
        step("tab1 add", lambda: t1.page.click("#add"), wait=3)
        r["entries"] = t1.page.locator(".entry").all_inner_texts()
        r["hash_end"] = short(t1.ls_hash())
        r["totals"] = counts(log, 0)
    except Exception as e:
        r["error"] = repr(e)[:300]
    finally:
        r["console_errors"] = [e for e in log if e.get("kind") == "pageerror" or (e.get("kind") == "console" and e.get("type") == "error" and "TUNNEL" not in (e.get("text") or ""))][:20]
        r["_full_log"] = log
        ctx.close()
    return r


def run_relogin(browser, base, label, rep):
    log = []
    ctx = new_context(browser, log)
    r = {"rep": rep}
    try:
        t = Tab(ctx, "tab", log)
        r["alice_login"] = login(t, base, "alice")
        wait_for(lambda: t.ls_hash(), 15)
        pause(1.5)
        h_alice = t.ls_hash()
        t.page.click("#add")
        wait_for(lambda: t.text("#clicks", 500) == "1", 10)
        t.page.reload()
        wait_hydrated(t)
        pause(3)
        r["alice_after_reload"] = [t.text("#who", 1000), t.text("#clicks", 1000), t.page.locator(".entry").all_inner_texts()]
        t.page.click("#logout")
        t.page.wait_for_url(IDP + "/oauth2/end_session**", timeout=30000)
        t.page.get_by_role("button", name="End session").click()
        wait_for(lambda: t.page.url.startswith(base) and t.path() == "/", 30)
        pause(3)
        r["after_logout"] = {"who": t.text("#who", 1000), "hash": short(t.ls_hash()), "cookies": oidc_cookies(ctx)}
        r["bob_login"] = login(t, base, "bob")
        pause(3)
        h_bob = t.ls_hash()
        r["bob_view"] = [t.text("#who", 1000), t.text("#clicks", 1000), t.page.locator(".entry").all_inner_texts()]
        r["hash_changed"] = bool(h_bob) and h_bob != h_alice
        t.page.reload()
        wait_hydrated(t)
        pause(3)
        r["bob_after_reload"] = [t.text("#who", 1000), t.path()]
        t.page.click("#add")
        pause(3)
        r["bob_entries"] = t.page.locator(".entry").all_inner_texts()
        t2 = Tab(ctx, "tab2", log)
        t2.page.goto(base + "/vault")
        pause(5)
        r["newtab"] = [t2.text("#who", 1000), t2.path()]
        r["ok"] = (
            r["alice_after_reload"][0] == "alice"
            and r["after_logout"]["who"] == ""
            and r["bob_view"][0] == "bob"
            and not any("alice" in x for x in r["bob_view"][2] + r["bob_entries"])
            and r["bob_after_reload"][0] == "bob"
            and any("bob" in x for x in r["bob_entries"])
            and r["newtab"][0] == "bob"
            and r["hash_changed"]
        )
        t.page.screenshot(path=str(SHOTS / f"{label}-relogin-{rep}.png"))
        r["totals"] = counts(log, 0)
    except Exception as e:
        r["error"] = repr(e)[:300]
    finally:
        r["console_errors"] = [e for e in log if e.get("kind") == "pageerror" or (e.get("kind") == "console" and e.get("type") == "error" and "TUNNEL" not in (e.get("text") or ""))][:20]
        r["_full_log"] = log
        ctx.close()
    return r




def run_pubslash(browser, base, label, rep):
    """Anonymous direct loads of the PUBLIC pages (/pid, /pid/, /) and of /vault: where does each end up?"""
    log = []
    ctx = new_context(browser, log)
    r = {"rep": rep, "loads": {}}
    try:
        t = Tab(ctx, "pub", log)
        for path in ("/pid", "/pid/", "/", "/vault"):
            i = len(log)
            t.page.goto(base + path)
            pause(5)
            r["loads"][path] = {"final": t.page.url.replace(base, ""), "pid_text": t.text("#pid", 500), **counts(log, i)}
            r["loads"][path]["chained"] = [c for e in log[i:] if e.get("kind") == "ws" for c in (e.get("chained") or [])]
    except Exception as e:
        r["error"] = repr(e)[:300]
    finally:
        r["_full_log"] = log
        ctx.close()
    return r
def main():
    mode, base, label, n = sys.argv[1], sys.argv[2].rstrip("/"), sys.argv[3], int(sys.argv[4])
    OUT.mkdir(exist_ok=True)
    SHOTS.mkdir(exist_ok=True)
    fn = {"fresh": run_fresh, "loads": run_loads, "relogin": run_relogin, "pubslash": run_pubslash}[mode]
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        try:
            for rep in range(n):
                res = fn(browser, base, label, rep)
                results.append(res)
                print(json.dumps({k: v for k, v in res.items() if not k.endswith("_log") and k != "console_errors"}, default=str), flush=True)
        finally:
            browser.close()
    out = OUT / f"{label}-hunt-{mode}.json"
    out.write_text(json.dumps(results, indent=1, default=str))
    if mode == "relogin":
        print(f"SUMMARY {label} relogin: ok {sum(1 for r in results if r.get('ok'))}/{len(results)}")
    else:
        print(f"SUMMARY {label} {mode}: see per-step counts above")
    print("wrote", out)


if __name__ == "__main__":
    vdrv.OUT.mkdir(exist_ok=True)
    main()
