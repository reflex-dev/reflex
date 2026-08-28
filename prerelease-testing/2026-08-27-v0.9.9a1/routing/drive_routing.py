"""Playwright driver for the routing cluster test app (reflex 0.9.9a1).

Usage:
    python drive_routing.py [base_url] [shots_dir] [test1,test2,...]

Defaults: base_url=http://localhost:3100, shots_dir=./shots, all tests.
Prints a JSON results array at the end (line prefixed RESULTS_JSON:).
"""

import json
import sys
import time

from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:3100"
SHOTS = sys.argv[2] if len(sys.argv) > 2 else "shots"
ONLY = sys.argv[3].split(",") if len(sys.argv) > 3 else None

import os

os.makedirs(SHOTS, exist_ok=True)

BENIGN_CONSOLE = (
    "HydrateFallback",
    "[vite] connecting",
    "[vite] connected",
    "React DevTools",
    "Download the React DevTools",
)

results = []


class Recorder:
    """Collect console messages and bad responses for one page."""

    def __init__(self, page, label):
        self.label = label
        self.console = []
        self.failed = []
        self.bad = []
        page.on("console", lambda m: self.console.append((m.type, m.text)))
        page.on("pageerror", lambda e: self.console.append(("pageerror", str(e))))
        page.on("requestfailed", lambda r: self.failed.append((r.url, str(r.failure))))
        page.on(
            "response",
            lambda r: self.bad.append((r.status, r.url)) if r.status >= 400 else None,
        )

    def anomalies(self):
        out = [
            f"[{t}] {m}"
            for t, m in self.console
            if t in ("error", "warning", "pageerror")
            and not any(b in m for b in BENIGN_CONSOLE)
        ]
        out += [f"[requestfailed] {u} {f}" for u, f in self.failed]
        out += [f"[http{s}] {u}" for s, u in self.bad]
        return out


def record(name, status, details):
    results.append({"name": name, "status": status, "details": details})
    print(f"== {name}: {status} :: {details}", flush=True)


def txt(page, sel):
    return page.locator(sel).inner_text(timeout=5000)


def wait_heading(page, expected, timeout=10000):
    page.wait_for_function(
        "exp => document.querySelector('#page-heading') && document.querySelector('#page-heading').innerText === exp",
        arg=expected,
        timeout=timeout,
    )


def goto(page, path, heading=None):
    page.goto(BASE + path, wait_until="load", timeout=30000)
    if heading:
        wait_heading(page, heading)
    page.wait_for_timeout(300)


def nav_click(page, link_id, heading=None):
    t0 = time.time()
    page.click(f"#{link_id}")
    if heading:
        wait_heading(page, heading)
    return time.time() - t0


def wait_ws(page):
    """Wait until state is hydrated (visits box exists and backend responded)."""
    page.wait_for_selector("#visits", state="attached", timeout=15000)
    page.wait_for_timeout(800)


def test_basic(ctx):
    page = ctx.new_page()
    rec = Recorder(page, "basic")
    goto(page, "/", "HOME")
    wait_ws(page)
    page.screenshot(path=f"{SHOTS}/01_home.png")
    an = rec.anomalies()
    record(
        "basic-load-home",
        "pass" if not an else "anomaly",
        f"home page loaded; console/network anomalies: {an or 'none'}",
    )
    page.close()
    return an


def test_splat(ctx):
    # 6790: /postsomething must NOT be captured by posts/[[...splat]]
    page = ctx.new_page()
    rec = Recorder(page, "splat")

    # direct load of /postsomething
    goto(page, "/postsomething", "POSTSOMETHING")
    wait_ws(page)
    page.wait_for_timeout(1000)
    visits = txt(page, "#visits")
    page.screenshot(path=f"{SHOTS}/02_postsomething.png")
    ok = "postsomething" in visits and "posts-catchall" not in visits
    record(
        "splat-6790-direct-postsomething",
        "pass" if ok else "fail",
        f"direct goto /postsomething -> heading POSTSOMETHING, visits={visits!r} "
        "(must contain postsomething on_load and NOT posts-catchall on_load)",
    )

    # /posts (catchall with empty splat)
    page.click("#nav-posts")
    wait_heading(page, "POSTS-CATCHALL")
    page.wait_for_timeout(800)
    visits = txt(page, "#visits")
    splat = txt(page, "#splat-args")
    ok = "posts-catchall" in visits and "path=/posts" in visits
    record(
        "splat-catchall-root",
        "pass" if ok else "fail",
        f"client-nav to /posts -> catchall page, splat box={splat!r}, visits={visits!r}",
    )

    # /posts/a/b deep link
    goto(page, "/posts/a/b", "POSTS-CATCHALL")
    page.wait_for_timeout(800)
    splat = txt(page, "#splat-args")
    visits = txt(page, "#visits")
    page.screenshot(path=f"{SHOTS}/03_posts_a_b.png")
    ok = "a,b" in splat and "path=/posts/a/b" in visits
    record(
        "splat-catchall-deep",
        "pass" if ok else "fail",
        f"direct goto /posts/a/b -> splat box={splat!r}, visits tail={visits[-200:]!r}",
    )

    # client-side nav to /postsomething from catchall page
    page.evaluate("document.querySelector('#visits').innerText")
    page.click("#nav-postsomething")
    wait_heading(page, "POSTSOMETHING")
    page.wait_for_timeout(800)
    visits = txt(page, "#visits")
    tail = visits.split(" ; ")[-1] if visits else ""
    ok = "postsomething" in tail and "catchall" not in tail
    record(
        "splat-6790-clientnav-postsomething",
        "pass" if ok else "fail",
        f"client-nav catchall->/postsomething, last visit entry={tail!r}",
    )
    an = rec.anomalies()
    if an:
        record("splat-console", "anomaly", f"console/network during splat tests: {an}")
    page.close()


def test_static_dynamic(ctx):
    # 6953 browser side: static 'all' resolves over dynamic [id]
    page = ctx.new_page()
    rec = Recorder(page, "staticdyn")
    goto(page, "/articles/all/5", "ARTICLES-ALL-STATIC")
    wait_ws(page)
    page.wait_for_timeout(600)
    x = txt(page, "#x-arg")
    visits = txt(page, "#visits")
    page.screenshot(path=f"{SHOTS}/04_articles_all_5.png")
    ok = "5" in x and "articles-all" in visits and "articles-id" not in visits
    record(
        "staticdyn-6953-static-wins-direct",
        "pass" if ok else "fail",
        f"direct goto /articles/all/5 -> heading ARTICLES-ALL-STATIC, x={x!r}, visits={visits!r}",
    )

    goto(page, "/articles/7", "ARTICLE-DYNAMIC")
    page.wait_for_timeout(600)
    idv = txt(page, "#id-arg")
    ok = "7" in idv
    record(
        "staticdyn-dynamic-id-direct",
        "pass" if ok else "fail",
        f"direct goto /articles/7 -> heading ARTICLE-DYNAMIC, id box={idv!r}",
    )

    # /articles/all (2 segments) should match [id] with id='all'
    goto(page, "/articles/all")
    page.wait_for_timeout(600)
    heading = txt(page, "#page-heading")
    idv = txt(page, "#id-arg") if heading == "ARTICLE-DYNAMIC" else "n/a"
    record(
        "staticdyn-articles-all-2seg",
        "pass" if heading == "ARTICLE-DYNAMIC" and "all" in idv else "anomaly",
        f"/articles/all resolves to heading={heading!r} id={idv!r} "
        "(expected dynamic [id] page with id=all since static route needs 3 segments)",
    )

    # client-side nav between the two siblings
    page.click("#nav-art-all-5")
    wait_heading(page, "ARTICLES-ALL-STATIC")
    page.wait_for_timeout(400)
    x = txt(page, "#x-arg")
    record(
        "staticdyn-static-wins-clientnav",
        "pass" if "5" in x else "fail",
        f"client-nav to /articles/all/5 -> x box={x!r}",
    )
    an = rec.anomalies()
    if an:
        record("staticdyn-console", "anomaly", f"console/network: {an}")
    page.close()


def test_slow_onload_cancel(ctx):
    # 6593: navigate away mid slow on_load; stale chain must be cancelled
    page = ctx.new_page()
    rec = Recorder(page, "slowcancel")
    goto(page, "/", "HOME")
    wait_ws(page)
    page.click("#btn-clear-slow") if page.locator("#btn-clear-slow").count() else None

    t_nav = nav_click(page, "nav-slow", "SLOW")
    # wait until load1-step1 lands (~1s)
    page.wait_for_function(
        "() => document.querySelector('#slow-progress').innerText.includes('-step1')",
        timeout=8000,
    )
    progress_at_nav = txt(page, "#slow-progress")
    page.screenshot(path=f"{SHOTS}/05_slow_midload.png")

    # navigate away immediately
    t_other = nav_click(page, "nav-other", "OTHER")
    page.wait_for_function(
        "() => document.querySelector('#visits').innerText.includes('|other|')",
        timeout=8000,
    )
    t_visit = time.time()
    t0 = time.time()
    # wait long enough that steps 3/4 would land if the chain survived
    page.wait_for_timeout(5000)
    progress_after = txt(page, "#slow-progress")
    page.screenshot(path=f"{SHOTS}/06_other_after_cancel.png")

    stale_completed = "load1-step4" in progress_after
    new_steps = [
        s
        for s in progress_after.split(" ; ")
        if s and s not in progress_at_nav.split(" ; ")
    ]
    record(
        "onload-6593-stale-chain-cancelled",
        "fail" if stale_completed else "pass",
        f"on /slow, at nav-away progress={progress_at_nav!r}; 5s after landing on /other "
        f"progress={progress_after!r}; entries appended after navigation: {new_steps} "
        f"(load1-step4 present would mean stale chain survived)",
    )
    record(
        "onload-6593-new-page-prompt",
        "pass" if t_other < 3.0 else "fail",
        f"time from clicking nav-other until OTHER heading rendered: {t_other:.2f}s; "
        "on_load visit entry appeared right after (must not wait for the 4s slow chain)",
    )

    # navigate back and let it complete fully
    page.click("#nav-slow")
    wait_heading(page, "SLOW")
    page.wait_for_function(
        "() => /load\\d+-step4/.test(document.querySelector('#slow-progress').innerText)",
        timeout=10000,
    )
    progress_full = txt(page, "#slow-progress")
    latest = progress_full.split(" ; ")[-1]
    ok = "-step4" in latest
    record(
        "onload-6593-uninterrupted-completes",
        "pass" if ok else "fail",
        f"revisit /slow without navigating away: progress={progress_full!r} (latest load reaches step4)",
    )
    an = rec.anomalies()
    if an:
        record("slowcancel-console", "anomaly", f"console/network: {an}")
    page.close()


def test_bg_onload(ctx):
    # on_load as background task + navigate away: record observed behavior
    page = ctx.new_page()
    rec = Recorder(page, "bgload")
    goto(page, "/", "HOME")
    wait_ws(page)
    page.click("#nav-slowbg")
    wait_heading(page, "SLOWBG")
    page.wait_for_function(
        "() => document.querySelector('#bg-progress').innerText.includes('bg1-start')",
        timeout=8000,
    )
    page.click("#nav-other")
    wait_heading(page, "OTHER")
    page.wait_for_timeout(5500)
    bg = txt(page, "#bg-progress")
    page.screenshot(path=f"{SHOTS}/07_bg_after_nav.png")
    survived = "bg1-step4" in bg
    record(
        "onload-background-task-nav-away",
        "pass",
        f"on_load background task, navigated away after start: bg_progress={bg!r} -> "
        f"{'background task SURVIVED navigation (completed all steps)' if survived else 'background task was cancelled/stopped'}",
    )
    an = rec.anomalies()
    if an:
        record("bgload-console", "anomaly", f"console/network: {an}")
    page.close()


def test_supersedes_button(ctx):
    # supersedes=True on a normal button: rapid clicks -> only latest completes
    page = ctx.new_page()
    rec = Recorder(page, "supersede")
    goto(page, "/", "HOME")
    wait_ws(page)
    page.click("#btn-clear-clicks")
    page.wait_for_timeout(400)

    for _ in range(4):
        page.click("#btn-supersede")
        page.wait_for_timeout(150)
    page.wait_for_timeout(3500)
    started = txt(page, "#click-started")
    res = txt(page, "#click-results")
    page.screenshot(path=f"{SHOTS}/08_supersede_clicks.png")
    done = [s for s in res.split(" ; ") if "-done" in s]
    ok = len(done) == 1
    record(
        "supersedes-button-rapid-clicks",
        "pass" if ok else "fail",
        f"4 rapid clicks on supersedes=True handler: started counter={started!r}, "
        f"completions={done} (expected exactly 1 completion, the latest)",
    )

    # baseline: normal handler, all clicks complete
    page.click("#btn-clear-clicks")
    page.wait_for_timeout(400)
    for _ in range(3):
        page.click("#btn-normal")
        page.wait_for_timeout(150)
    page.wait_for_timeout(3500)
    nres = txt(page, "#click-normal-results")
    ndone = [s for s in nres.split(" ; ") if "normal-done" in s]
    record(
        "no-supersedes-button-baseline",
        "pass" if len(ndone) == 3 else "fail",
        f"3 rapid clicks on plain handler: completions={len(ndone)} ({nres!r}) — expected all 3",
    )

    # single click on supersedes handler completes normally
    page.click("#btn-clear-clicks")
    page.wait_for_timeout(400)
    page.click("#btn-supersede")
    page.wait_for_timeout(2500)
    res = txt(page, "#click-results")
    record(
        "supersedes-single-click-completes",
        "pass" if "-done" in res else "fail",
        f"single click on supersedes handler completes: results={res!r}",
    )
    an = rec.anomalies()
    if an:
        record("supersede-console", "anomaly", f"console/network: {an}")
    page.close()


def test_chained_routing_two_tabs(ctx):
    # 6919: two tabs on different dynamic values; chained event sees own args
    a = ctx.new_page()
    b = ctx.new_page()
    ra, rb = Recorder(a, "tabA"), Recorder(b, "tabB")
    goto(a, "/articles/1", "ARTICLE-DYNAMIC")
    wait_ws(a)
    goto(b, "/articles/2", "ARTICLE-DYNAMIC")
    wait_ws(b)
    ida, idb = txt(a, "#id-arg"), txt(b, "#id-arg")
    a.click("#btn-clear-chain")
    b.click("#btn-clear-chain")
    a.wait_for_timeout(300)

    a.click("#btn-chain")
    a.wait_for_timeout(200)
    b.click("#btn-chain")
    a.wait_for_timeout(3500)
    log_a = txt(a, "#chain-log")
    log_b = txt(b, "#chain-log")
    a.screenshot(path=f"{SHOTS}/09_chain_tab_a.png")
    b.screenshot(path=f"{SHOTS}/10_chain_tab_b.png")
    ok_a = "record[chained]:path=/articles/1:id=1" in log_a
    ok_b = "record[chained]:path=/articles/2:id=2" in log_b
    shared = log_a == log_b and "id=1" in log_a and "id=2" in log_a
    record(
        "chained-6919-two-tabs-own-args",
        "pass" if ok_a and ok_b else "fail",
        f"tab A on /articles/1 id-box={ida!r} chain_log={log_a!r}; "
        f"tab B on /articles/2 id-box={idb!r} chain_log={log_b!r}; "
        f"{'NOTE: tabs share one state token' if shared else 'tabs have separate state tokens'} "
        "(each chained record must resolve id/path of its own view)",
    )
    an = ra.anomalies() + rb.anomalies()
    if an:
        record("chained-two-tabs-console", "anomaly", f"console/network: {an}")
    a.close()
    b.close()


def test_chained_routing_nav_race(ctx):
    # 6919 sharpest case: fire chain on /articles/1, navigate to /articles/2
    # before the chained event processes; it must still resolve id=1.
    page = ctx.new_page()
    rec = Recorder(page, "chainrace")
    goto(page, "/articles/1", "ARTICLE-DYNAMIC")
    wait_ws(page)
    page.click("#btn-clear-chain")
    page.wait_for_timeout(300)
    page.click("#btn-chain")
    page.wait_for_timeout(300)
    # client-side nav to the other article while chain sleeps 2s
    page.click("#nav-art-2")
    wait_heading(page, "ARTICLE-DYNAMIC")
    page.wait_for_timeout(4000)
    log = txt(page, "#chain-log")
    idv = txt(page, "#id-arg")
    visits = txt(page, "#visits")
    page.screenshot(path=f"{SHOTS}/11_chain_nav_race.png")
    entries = [e for e in log.split(" ; ") if "record[chained]" in e]
    ok = any("path=/articles/1:id=1" in e for e in entries)
    wrong = any("id=2" in e for e in entries)
    record(
        "chained-6919-nav-race-inherits-producer-view",
        "pass" if ok and not wrong else "fail",
        f"clicked start-chain on /articles/1 then client-nav to /articles/2 during the 2s sleep; "
        f"chained record entries={entries!r} (must say path=/articles/1:id=1, NOT id=2); "
        f"current page id-box={idv!r}; visits tail={visits[-150:]!r}; full chain_log={log!r}",
    )
    an = rec.anomalies()
    if an:
        record("chainrace-console", "anomaly", f"console/network: {an}")
    page.close()


TESTS = {
    "basic": test_basic,
    "splat": test_splat,
    "staticdyn": test_static_dynamic,
    "slowcancel": test_slow_onload_cancel,
    "bg": test_bg_onload,
    "supersede": test_supersedes_button,
    "chain2tabs": test_chained_routing_two_tabs,
    "chainrace": test_chained_routing_nav_race,
}

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = browser.new_context()
    for name, fn in TESTS.items():
        if ONLY and name not in ONLY:
            continue
        try:
            fn(ctx)
        except Exception as e:
            record(f"{name}-EXCEPTION", "fail", f"driver exception: {e!r}")
            try:
                pg = ctx.pages[-1] if ctx.pages else None
                if pg:
                    pg.screenshot(path=f"{SHOTS}/EXC_{name}.png")
            except Exception:
                pass
    browser.close()

print("RESULTS_JSON:" + json.dumps(results))
