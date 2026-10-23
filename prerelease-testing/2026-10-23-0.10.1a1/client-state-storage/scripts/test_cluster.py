"""Playwright scenarios for the client-state-storage cluster.

Usage (driver venv, proxy bypassed):
  NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
    $SB/envs/driver/bin/python test_cluster.py http://localhost:3140 <scenario|all> --tag <label>

Scenarios: client_state, sync, computed, bloat, expire
Writes shots/<tag>-*.png and logs/<tag>-<scenario>.json (console, errors, failed requests, results).
"""
import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

CHROMIUM = "/opt/pw-browsers/chromium"
A = Path(__file__).resolve().parent.parent  # outputs land in A/shots and A/logs, outside app/ (the reflex reloader watches app subdirs)
BENIGN = [re.compile(r"Hey developer.*HydrateFallback|reactrouter\.com/start/framework/route-module"),
          re.compile(r"\[vite\] (connecting|connected)"), re.compile(r"Download the React DevTools")]

BASE = sys.argv[1].rstrip("/")
SCEN = sys.argv[2]
TAG = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "run"


class Capture:
    def __init__(self):
        self.console = []
        self.errors = []
        self.failed = []
        self.ws_opens = []
        self.results = {}

    def attach(self, page, label):
        page.on("console", lambda m: self.console.append({"page": label, "type": m.type, "text": m.text})
                if not any(b.search(m.text) for b in BENIGN) else None)
        page.on("pageerror", lambda e: self.errors.append({"page": label, "error": str(e)}))
        page.on("requestfailed", lambda r: self.failed.append({"page": label, "url": r.url, "failure": r.failure}))
        page.on("response", lambda r: self.failed.append({"page": label, "url": r.url, "status": r.status})
                if r.status >= 400 else None)
        page.on("websocket", lambda ws: self.ws_opens.append({"page": label, "t": time.monotonic(), "url": ws.url})
                if "/_event" in ws.url else None)

    def check(self, name, cond, detail=""):
        self.results[name] = {"ok": bool(cond), "detail": str(detail)}
        print(("PASS " if cond else "FAIL ") + name + (f" :: {detail}" if detail else ""), flush=True)

    def dump(self, scen):
        out = A / "logs" / f"{TAG}-{scen}.json"
        out.write_text(json.dumps({"console": self.console, "errors": self.errors, "failed": self.failed,
                                   "ws_opens": self.ws_opens, "results": self.results}, indent=1, default=str))
        print("report:", out, flush=True)


def shot(page, name):
    page.screenshot(path=str(A / "shots" / f"{TAG}-{name}.png"), full_page=True)


def txt(page, sel, timeout=10000):
    loc = page.locator(sel)
    loc.wait_for(timeout=timeout, state="attached")
    return (loc.text_content() or "").strip()


def wait_hydrated(page, sel="#hydrated"):
    expect(page.locator(sel)).to_have_text("true", timeout=30000)


def scen_client_state(p, cap):
    ctx = p.chromium.launch(executable_path=CHROMIUM).new_context()
    page = ctx.new_page(); cap.attach(page, "cs")
    page.goto(BASE + "/")
    expect(page.locator("#token")).not_to_have_text("", timeout=30000)
    expect(page.locator("#load-count")).to_have_text("1", timeout=15000)
    # #7407 case 2: on_load pushed before pushed-reader mounted (behind cond).
    page.click("#reveal")
    v = txt(page, "#pushed-reader")
    cap.check("push_before_mount_from_on_load", v == "pushed-on-load-1", v)
    cap.check("late_reader_default", txt(page, "#late-reader") == "initial", txt(page, "#late-reader"))
    # background task pushes before its reader mounts
    page.click("#bg-pusher")
    expect(page.locator("#bg-status")).to_have_text("pushed", timeout=10000)
    page.wait_for_timeout(300)
    page.click("#reveal-bg")
    v = txt(page, "#pushed-bg-reader")
    cap.check("push_before_mount_from_background", v == "pushed-from-bg", v)
    shot(page, "cs-after-reveal")
    # readers in sync: always, memo, foreach, late
    page.click("#setter")
    expect(page.locator("#late-reader")).to_have_text("clicked")
    rd = {k: txt(page, k) for k in ["#always-reader", "#memo-reader", "#late-reader"]}
    fr = page.locator(".foreach-reader").all_inner_texts()
    cap.check("all_readers_clicked", all(v == "clicked" for v in rd.values()) and all(f.endswith("=clicked") for f in fr), f"{rd} {fr}")
    # push default then push non-default then push None
    page.click("#push-default")
    expect(page.locator("#pushed-reader")).to_have_text("not-pushed")
    page.click("#pusher")
    expect(page.locator("#pushed-reader")).to_have_text("pushed-by-click")
    page.click("#push-none")
    page.wait_for_timeout(300)
    cap.check("push_none_renders_empty", txt(page, "#pushed-reader") == "", repr(txt(page, "#pushed-reader")))
    # #7407 case 1: late-mounted reader, set to non-default, then back to default.
    page2 = ctx.new_page(); cap.attach(page2, "cs2")
    page2.goto(BASE + "/")
    expect(page2.locator("#load-count")).not_to_have_text("", timeout=30000)
    page2.click("#setter")
    page2.click("#reveal")
    expect(page2.locator("#late-reader")).to_have_text("clicked")
    page2.click("#resetter")
    page2.wait_for_timeout(300)
    rd = {k: txt(page2, k) for k in ["#always-reader", "#memo-reader", "#late-reader"]}
    cap.check("late_reader_set_back_to_default", all(v == "initial" for v in rd.values()), rd)
    shot(page2, "cs-late-reset")
    # cross-page client nav: does the value survive client-side navigation? (same SPA)
    page2.click("#setter")
    page2.click("#to-second")
    expect(page2.locator("#second-reader")).to_be_visible(timeout=15000)
    v = txt(page2, "#second-reader")
    cap.results["info_value_after_client_nav"] = {"ok": True, "detail": f"second-reader={v!r} (informational: per-page useState)"}
    page2.click("#setter2")
    expect(page2.locator("#second-reader")).to_have_text("clicked-second")
    page2.click("#pusher2")
    expect(page2.locator("#second-pushed-reader")).to_have_text("pushed-by-click")
    page2.click("#to-index")
    expect(page2.locator("#always-reader")).to_be_visible(timeout=15000)
    page2.wait_for_timeout(500)
    v = txt(page2, "#always-reader")
    cap.results["info_value_back_on_index"] = {"ok": True, "detail": f"always-reader={v!r}"}
    # navigating back runs on_load again -> pushes pushed-on-load-N
    page2.click("#reveal")
    v = txt(page2, "#pushed-reader")
    cap.check("on_load_push_after_nav_back", v.startswith("pushed-on-load-"), v)
    shot(page2, "cs-back-index")
    # Direct load of /second: a page with no setter mounted first.
    page3 = ctx.new_page(); cap.attach(page3, "cs3")
    page3.goto(BASE + "/second")
    expect(page3.locator("#second-reader")).to_have_text("initial", timeout=30000)
    page3.click("#pusher2")
    expect(page3.locator("#second-pushed-reader")).to_have_text("pushed-by-click")
    cap.check("second_page_direct", True)
    ctx.browser.close()


def scen_sync(p, cap):
    browser = p.chromium.launch(executable_path=CHROMIUM)
    ctx = browser.new_context()
    a = ctx.new_page(); cap.attach(a, "tabA")
    b = ctx.new_page(); cap.attach(b, "tabB")
    a.goto(BASE + "/storage"); wait_hydrated(a)
    b.goto(BASE + "/storage"); wait_hydrated(b)
    a.fill("#in-a", "hello")
    expect(a.locator("#out-a")).to_have_text("a=hello")
    # same tab: do the other vars sharing name "shared" update after a round trip? (informational)
    a.wait_for_timeout(800)
    same_tab = {k: txt(a, k) for k in ["#out-a", "#out-b", "#out-n"]}
    cap.results["info_same_tab_sharing_name"] = {"ok": True, "detail": str(same_tab)}
    # tab B: every var sharing "shared" must reflect "hello" (#7545)
    try:
        expect(b.locator("#out-a")).to_have_text("a=hello", timeout=8000)
        expect(b.locator("#out-b")).to_have_text("b=hello", timeout=8000)
        expect(b.locator("#out-n")).to_have_text("n=hello", timeout=8000)
        ok = True; detail = {k: txt(b, k) for k in ["#out-a", "#out-b", "#out-n"]}
    except AssertionError as e:
        ok = False; detail = {k: txt(b, k) for k in ["#out-a", "#out-b", "#out-n"]}
    cap.check("sync_all_sharing_vars_tabB_after_edit_a", ok, detail)
    shot(b, "sync-tabB-after-a")
    # edit via b in tab B; check tab A
    b.fill("#in-b", "world")
    try:
        expect(a.locator("#out-a")).to_have_text("a=world", timeout=8000)
        expect(a.locator("#out-b")).to_have_text("b=world", timeout=8000)
        expect(a.locator("#out-n")).to_have_text("n=world", timeout=8000)
        ok = True
    except AssertionError:
        ok = False
    cap.check("sync_all_sharing_vars_tabA_after_edit_b", ok, {k: txt(a, k) for k in ["#out-a", "#out-b", "#out-n"]})
    # non-sharing synced var
    a.fill("#in-other", "o1")
    try:
        expect(b.locator("#out-other")).to_have_text("other=o1", timeout=8000); ok = True
    except AssertionError:
        ok = False
    cap.check("sync_other_var", ok, txt(b, "#out-other"))
    # cookie / session storage behaviour: cookie shared within context after reload, session is per-tab
    a.fill("#in-cookie", "c1"); a.fill("#in-sess", "s1")
    expect(a.locator("#out-cookie")).to_have_text("cookie=c1")
    a.wait_for_timeout(500)
    b.reload(); wait_hydrated(b)
    cap.check("cookie_visible_in_tabB_after_reload", txt(b, "#out-cookie") == "cookie=c1", txt(b, "#out-cookie"))
    cap.check("session_not_shared_tabB", txt(b, "#out-sess") == "sess=", txt(b, "#out-sess"))
    a.reload(); wait_hydrated(a)
    cap.check("session_persists_tabA_reload", txt(a, "#out-sess") == "sess=s1", txt(a, "#out-sess"))
    ls = a.evaluate("JSON.stringify({shared: localStorage.getItem('shared'), other: localStorage.getItem('other')})")
    cap.results["info_localStorage"] = {"ok": True, "detail": ls}
    shot(a, "sync-tabA-final")
    browser.close()


def scen_computed(p, cap):
    browser = p.chromium.launch(executable_path=CHROMIUM)
    ctx = browser.new_context()
    page = ctx.new_page(); cap.attach(page, "computed")
    page.goto(BASE + "/storage"); wait_hydrated(page)
    page.evaluate("localStorage.setItem('shared', 'seed')")
    page.click("#reset-counts")
    expect(page.locator("#counts")).to_have_text("reset")
    # Full reload
    page.reload(); wait_hydrated(page)
    expect(page.locator("#derived")).to_have_text("derived(seed)")
    page.click("#read-counts")
    expect(page.locator("#counts")).to_contain_text("derived=")
    c1 = txt(page, "#counts")
    cap.check("computed_evals_per_full_reload", c1 == "derived=1 derived_cookie=1", c1)
    # Client-side navigation away and back
    page.click("#reset-counts"); expect(page.locator("#counts")).to_have_text("reset")
    page.click("#to-index"); expect(page.locator("#always-reader")).to_be_visible(timeout=15000)
    page.click("#to-storage"); expect(page.locator("#derived")).to_be_visible(timeout=15000)
    page.wait_for_timeout(500)
    page.click("#read-counts"); page.wait_for_timeout(300)
    c2 = txt(page, "#counts")
    cap.results["info_computed_evals_after_client_nav"] = {"ok": True, "detail": c2}
    # Unrelated event should not re-evaluate
    page.click("#reset-counts"); expect(page.locator("#counts")).to_have_text("reset")
    page.click("#bump"); expect(page.locator("#plain-counter")).to_have_text("1")
    page.click("#read-counts"); page.wait_for_timeout(300)
    c3 = txt(page, "#counts")
    cap.check("computed_not_reevaluated_on_unrelated_event", c3 == "derived=0 derived_cookie=0", c3)
    # Editing the dependency: exactly one eval
    page.fill("#in-a", "edit1")
    expect(page.locator("#derived")).to_have_text("derived(edit1)")
    page.click("#read-counts"); page.wait_for_timeout(300)
    c4 = txt(page, "#counts")
    cap.check("computed_one_eval_per_dep_change", c4 == "derived=1 derived_cookie=0", c4)
    shot(page, "computed")
    browser.close()


def scen_bloat(p, cap):
    browser = p.chromium.launch(executable_path=CHROMIUM)
    ctx = browser.new_context()
    page = ctx.new_page(); cap.attach(page, "bloat")
    page.goto(BASE + "/bloat"); wait_hydrated(page)
    page.click("#fill-big")
    expect(page.locator("#blob-len")).to_have_text("len=1100000", timeout=15000)
    page.wait_for_timeout(500)
    n = page.evaluate("(localStorage.getItem('bloat')||'').length")
    cap.check("bloat_written_to_localstorage", n == 1100000, n)
    cap.ws_opens.clear()
    t0 = time.monotonic()
    page.reload()
    try:
        expect(page.get_by_text("Reduce browser storage data and reload")).to_be_visible(timeout=15000)
        toast = page.get_by_text(re.compile("Hydration payload")).first.inner_text()
        ok = True
    except AssertionError:
        ok = False; toast = page.content()[:3000]
    cap.check("bloat_toast_shown", ok, toast)
    shot(page, "bloat-toast")
    page.wait_for_timeout(30000)
    n_open = len([w for w in cap.ws_opens if w["t"] >= t0])
    cap.check("bloat_no_reconnect_loop_30s", n_open <= 1, f"ws opens in 30s: {n_open}")
    still = page.get_by_text("Reduce browser storage data and reload").is_visible()
    cap.check("bloat_toast_persists_30s", still, still)
    cap.check("bloat_not_hydrated", txt(page, "#hydrated") == "false", txt(page, "#hydrated"))
    shot(page, "bloat-toast-30s")
    # Close the toast manually if there is a close button
    closers = page.locator("[data-close-button], button[aria-label='Close toast'], [aria-label='Close']")
    cap.results["info_toast_close_buttons"] = {"ok": True, "detail": closers.count()}
    # Recover
    page.evaluate("localStorage.removeItem('bloat')")
    page.reload(); wait_hydrated(page)
    cap.check("bloat_recover_after_shrink", txt(page, "#blob-len") == "len=0", txt(page, "#blob-len"))
    # mid-size (500k, under 1MB) should hydrate fine
    page.click("#fill-mid"); expect(page.locator("#blob-len")).to_have_text("len=500000"); page.wait_for_timeout(500)
    page.reload(); wait_hydrated(page)
    cap.check("bloat_500k_hydrates", txt(page, "#blob-len") == "len=500000", txt(page, "#blob-len"))
    page.click("#clear"); page.wait_for_timeout(500)
    browser.close()


def scen_expire(p, cap):
    # Requires server started with REFLEX_REDIS_TOKEN_EXPIRATION=3 (seconds) and memory state manager.
    browser = p.chromium.launch(executable_path=CHROMIUM)
    ctx = browser.new_context()
    page = ctx.new_page(); cap.attach(page, "expire")
    page.goto(BASE + "/expire"); wait_hydrated(page)
    expect(page.locator("#loads")).to_have_text("loads=1")
    page.fill("#in-note", "keepme"); expect(page.locator("#out-note")).to_have_text("note=keepme")
    page.click("#inc"); page.click("#inc"); expect(page.locator("#count")).to_have_text("count=2")
    token = txt(page, "#token")
    page.click("#slow")
    expect(page.locator("#bg-result")).to_have_text("bg=sleeping 8s")
    shot(page, "expire-before")
    # wait for expiry (3s) + task end (8s)
    expect(page.locator("#bg-result")).to_contain_text("done", timeout=20000)
    page.wait_for_timeout(1000)
    shot(page, "expire-after-bg")
    st = {k: txt(page, k) for k in ["#count", "#bg-result", "#loads", "#out-note", "#hydrated", "#token"]}
    cap.results["info_state_after_bg_rehydrate"] = {"ok": True, "detail": str(st)}
    cap.check("expire_count_reset_after_rehydrate", st["#count"] == "count=0", st["#count"])
    cap.check("expire_storage_kept", st["#out-note"] == "note=keepme", st["#out-note"])
    cap.check("expire_route_kept", page.url.endswith("/expire") or page.url.endswith("/expire/"), page.url)
    cap.check("expire_token_kept", st["#token"] == token, f"{token} -> {st['#token']}")
    ls = page.evaluate("localStorage.getItem('expire-note')")
    cap.check("expire_localstorage_kept", ls == "keepme", ls)
    # Next event: should run on_load again (loads -> 1 on the new tree, then maybe 2)
    page.click("#inc")
    page.wait_for_timeout(1500)
    st2 = {k: txt(page, k) for k in ["#count", "#loads", "#out-note"]}
    cap.results["info_state_after_next_event"] = {"ok": True, "detail": str(st2)}
    cap.check("expire_next_event_runs_on_load", st2["#loads"] == "loads=1", st2["#loads"])
    cap.check("expire_next_event_applies", st2["#count"] == "count=1", st2["#count"])
    tok2 = txt(page, "#token")
    cap.check("expire_token_restored_after_next_event", tok2 == token, f"{token} -> {tok2!r}")
    ls2 = page.evaluate("localStorage.getItem('expire-note')")
    cap.check("expire_storage_rendered_after_next_event", st2["#out-note"] == "note=keepme",
              f"rendered {st2['#out-note']!r} while localStorage={ls2!r}")
    shot(page, "expire-after-event")
    # Does a full reload bring the stored value back to the server?
    page.reload(); wait_hydrated(page)
    st3 = {k: txt(page, k) for k in ["#count", "#loads", "#out-note", "#token"]}
    cap.results["info_state_after_reload"] = {"ok": True, "detail": str(st3)}
    cap.check("expire_reload_restores_storage", st3["#out-note"] == "note=keepme", st3["#out-note"])
    # Repeat with a shorter task so the tree does not expire: no rehydrate expected
    page.click("#inc"); expect(page.locator("#count")).to_have_text("count=2")
    page.click("#slow"); page.wait_for_timeout(1500); page.click("#inc"); page.wait_for_timeout(1500); page.click("#inc")
    expect(page.locator("#bg-result")).to_contain_text("done", timeout=20000)
    page.wait_for_timeout(500)
    st4 = {k: txt(page, k) for k in ["#count", "#bg-result", "#out-note"]}
    cap.results["info_state_bg_with_activity"] = {"ok": True, "detail": str(st4)}
    cap.check("expire_no_rehydrate_when_tree_kept_alive", st4["#count"] == "count=4", st4["#count"])
    browser.close()


SCENS = {"client_state": scen_client_state, "sync": scen_sync, "computed": scen_computed,
         "bloat": scen_bloat, "expire": scen_expire}

with sync_playwright() as p:
    for name, fn in SCENS.items():
        if SCEN not in ("all", name):
            continue
        cap = Capture()
        try:
            fn(p, cap)
        except Exception as e:  # noqa: BLE001
            cap.results["EXCEPTION"] = {"ok": False, "detail": repr(e)}
            print("EXCEPTION", repr(e), flush=True)
        cap.dump(name)
        print(f"--- {name}: console non-benign={len(cap.console)} pageerrors={len(cap.errors)} failed={len(cap.failed)}", flush=True)
        for c in cap.console[:20]:
            print("  console:", c, flush=True)
        for e in cap.errors[:10]:
            print("  pageerror:", e, flush=True)
        for f in cap.failed[:10]:
            print("  failed:", f, flush=True)
