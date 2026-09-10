"""Playwright end-to-end checks for the hotpath app (ordering, hierarchy, interval, slow, hammer).

Usage (driver venv, proxy bypassed):
  NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python pw_hotpath.py \
      --url http://localhost:3180 --out logs/pw_hotpath_smoke --label smoke [--only ordering,hier,...]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pwlib import Capture, dump, launch, text_of, wait_text, watch_changes  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

RESULTS: list[dict] = []


def rec(name: str, status: str, details: str, **extra):
    RESULTS.append({"name": name, "status": status, "details": details, **extra})
    print(f"[{status.upper():7}] {name}: {details}", flush=True)


def seqs(log: str) -> list[str]:
    """'log=3:my0,4:my1' -> ['my0','my1'] and asserts seq numbers strictly increase."""
    body = log.split("=", 1)[1] if "=" in log else log
    items = [x for x in body.split(",") if x]
    nums = [int(x.split(":", 1)[0]) for x in items]
    assert nums == sorted(nums), f"seq not increasing: {items}"
    return [x.split(":", 1)[1] for x in items]


def seq_map(log: str) -> dict[str, int]:
    body = log.split("=", 1)[1] if "=" in log else log
    out = {}
    for x in body.split(","):
        if x:
            n, _, lab = x.partition(":")
            out[lab] = int(n)
    return out


def test_ordering(page, url, out):
    page.goto(f"{url}/ordering")
    page.wait_for_selector("#log")
    wait_text(page, "#log", lambda t: t.startswith("log="), 15)
    page.click("#clear")
    wait_text(page, "#log", lambda t: t == "log=", 5)

    # 1. multiple yields -> 3 progressive deltas, in order
    page.click("#multi_yield")
    changes = watch_changes(page, "#log", 1.5)
    final = text_of(page, "#log")
    labels = seqs(final)
    distinct = [c[1] for c in changes]
    ok = labels == ["my0", "my1", "my2"] and len(distinct) >= 3
    rec("ordering.multi_yield", "pass" if ok else "fail",
        f"final={labels} progressive_states={distinct}")
    page.screenshot(path=f"{out}/ordering_multi_yield.png")

    # 2. handler returning list of events (chain across states)
    page.click("#clear")
    wait_text(page, "#log", lambda t: t == "log=", 5)
    page.click("#chain")
    wait_text(page, "#log", lambda t: "after-chain" in t, 5)
    time.sleep(0.3)
    log, olog = text_of(page, "#log"), text_of(page, "#other_log")
    sm = seq_map(log); om = seq_map(olog)
    ok = ("chain-start" in sm and "after-chain" in sm and "bump:from-chain" in om
          and sm["chain-start"] < om["bump:from-chain"] < sm["after-chain"])
    rec("ordering.chain_list_of_events", "pass" if ok else "fail",
        f"log={log} other_log={olog} (expected chain-start < bump:from-chain < after-chain)")

    # 3. yield Other.handler() from inside a handler
    page.click("#clear")
    wait_text(page, "#log", lambda t: t == "log=", 5)
    page.click("#yield_other")
    wait_text(page, "#other_log", lambda t: "yield-other" in t, 5)
    time.sleep(0.3)
    log, olog = text_of(page, "#log"), text_of(page, "#other_log")
    sm = seq_map(log); om = seq_map(olog)
    ok = "yo-start" in sm and "yo-end" in sm and "bump:yield-other" in om and sm["yo-start"] < sm["yo-end"] < om["bump:yield-other"]
    rec("ordering.yield_other_state_handler", "pass" if ok else "fail",
        f"log={log} other_log={olog} (expected yo-start < yo-end < bump: yielded event round-trips via client)")

    # 4. yield, sleep, yield -> deltas arrive in order and progressively
    page.click("#clear")
    wait_text(page, "#log", lambda t: t == "log=", 5)
    page.click("#ysy")
    changes = watch_changes(page, "#log", 1.6)
    states = [seqs(c[1]) for c in changes if c[1] != "log="]
    ok = states[-1:] == [["ysy-a", "ysy-b", "ysy-c"]] and len(states) >= 3 and states[0] == ["ysy-a"] and states[1] == ["ysy-a", "ysy-b"]
    rec("ordering.yield_sleep_yield", "pass" if ok else "fail", f"observed={changes}")

    # 5. rapid clicks on two different buttons -> order preserved (20 rounds, JS-synchronous clicks)
    page.click("#clear")
    wait_text(page, "#log", lambda t: t == "log=", 5)
    pattern = []
    for i in range(20):
        pair = ["a", "b"] if i % 3 else ["b", "a"]
        pattern += [p.upper() for p in pair]
        page.evaluate("(ids) => { for (const id of ids) document.getElementById(id).click(); }", pair)
    final = wait_text(page, "#log", lambda t: t.count(":") >= 40, 10)
    labels = seqs(final)
    rec("ordering.rapid_two_buttons", "pass" if labels == pattern else "fail",
        f"got {len(labels)} entries; match={labels == pattern}; first_diff={next((i for i,(x,y) in enumerate(zip(labels,pattern)) if x!=y), None)}")

    # 6. background task interleaved with foreground handlers + StateProxy get_state/get_var_value/parent_state
    page.click("#clear")
    wait_text(page, "#log", lambda t: t == "log=", 5)
    page.click("#bg")
    time.sleep(0.15)
    page.click("#fg1"); time.sleep(0.12)
    page.click("#fg2"); time.sleep(0.12)
    page.click("#fg3")
    final = wait_text(page, "#log", lambda t: "bg-end" in t, 8)
    labels = seqs(final)
    other_val = text_of(page, "#other_val")
    fg = [x for x in labels if x.startswith("fg:")]
    bg_mid = [x for x in labels if x.startswith("bg-mid")]
    ok = (fg == ["fg:1", "fg:2", "fg:3"] and labels[0] == "bg-start" and labels[-1] == "bg-end"
          and bg_mid and labels.index("bg-start") < labels.index(bg_mid[0]) < labels.index("bg-end")
          and labels.index("fg:3") < labels.index(bg_mid[0])
          and "other_val=100" in other_val and "parent=State" in bg_mid[0])
    rec("ordering.background_interleave_stateproxy", "pass" if ok else "fail",
        f"labels={labels} other_val={other_val}")
    page.screenshot(path=f"{out}/ordering_bg.png")


def test_hier(page, url, out):
    page.goto(f"{url}/hier")
    page.wait_for_selector("#report")
    wait_text(page, "#root_val", lambda t: t == "root_val=1", 15)
    page.click("#read_parents")
    rep = wait_text(page, "#report", lambda t: "leaf=" in t, 5)
    ok = ("leaf=100 mid=10 root=1 inh_mid=10 inh_root=1" in rep and "pname=" in rep and "mid3" in rep and "root3" in rep and "full=" in rep)
    rec("hier.read_via_parent_state_3deep", "pass" if ok else "fail", rep)
    page.click("#write_via_parent")
    m = wait_text(page, "#mid_val", lambda t: t == "mid_val=11", 5)
    r = text_of(page, "#root_val"); li = text_of(page, "#leaf_inh_root")
    ok = m == "mid_val=11" and r == "root_val=2" and li == "leaf_inh_root=2"
    rec("hier.write_via_parent_state_delta", "pass" if ok else "fail", f"{m} {r} {li}")
    page.click("#write_inherited")
    m = wait_text(page, "#mid_val", lambda t: t == "mid_val=12", 5)
    r = text_of(page, "#root_val")
    rec("hier.write_inherited_vars", "pass" if (m == "mid_val=12" and r == "root_val=3") else "fail", f"{m} {r}")
    page.click("#bg_read_parents")
    rep = wait_text(page, "#report", lambda t: t.startswith("report=bg"), 5)
    lv = wait_text(page, "#leaf_val", lambda t: t == "leaf_val=101", 5)
    ok = "bg leaf=100 mid=12 root=3" in rep and lv == "leaf_val=101"
    rec("hier.background_parent_state_read", "pass" if ok else "fail", f"{rep} {lv}")
    page.screenshot(path=f"{out}/hier.png")


def test_backend(page, url, out):
    page.goto(f"{url}/backend")
    page.wait_for_selector("#shown")
    wait_text(page, "#shown", lambda t: t.startswith("shown="), 15)
    page.click("#reset_backend"); time.sleep(0.3)
    page.click("#bump_hidden")
    s1 = wait_text(page, "#shown", lambda t: "hidden=1" in t, 5)
    page.click("#bump_hidden")
    s2 = wait_text(page, "#shown", lambda t: "hidden=2" in t, 5)
    ok = "hidden=2 items=[1, 2]" in s2 and "_hidden" in s2 and "_items" in s2
    rec("backend.backend_vars_read_write_inplace", "pass" if ok else "fail", f"{s1} -> {s2}")
    if "gwt=n/a" not in s2:
        rec("backend.backend_var_named__get_was_touched", "pass" if "gwt=9" in s2 else "fail", s2)
    # reload the page: backend vars must survive (state persisted by the state manager)
    page.reload(); page.wait_for_selector("#shown")
    wait_text(page, "#shown", lambda t: t.startswith("shown="), 15)
    page.click("#bump_hidden")
    s3 = wait_text(page, "#shown", lambda t: "hidden=3" in t, 5)
    rec("backend.backend_vars_survive_reload", "pass" if "hidden=3 items=[1, 2, 3]" in s3 else "fail", s3)
    page.screenshot(path=f"{out}/backend.png")


def toasts(page) -> list[str]:
    try:
        return [t.inner_text().replace("\n", " ")[:300] for t in page.locator("[data-sonner-toast]").all()]
    except Exception:  # noqa: BLE001
        return []


def test_shadow(page, url, out):
    page.goto(f"{url}/shadow")
    page.wait_for_selector("#shadow_get_state")
    v0 = wait_text(page, "#shadow_get_state", lambda t: t.startswith("get_state="), 15)
    # a var named `get_state` (an async framework method users call explicitly)
    page.click("#set_shadow")
    v1 = wait_text(page, "#shadow_get_state", lambda t: t.startswith("get_state=set-"), 5)
    n1 = text_of(page, "#shadow_note"); time.sleep(0.5); tl = toasts(page)
    ok = v0 == "get_state=shadow-initial" and v1.startswith("get_state=set-") and not tl
    rec("shadow.var_named_get_state", "pass" if ok else "fail", f"{v0} -> {v1}; {n1}; toasts={tl}")
    # a var named `get_delta` (a framework method the event loop calls on every event)
    page.click("#bump_delta")
    d1 = wait_text(page, "#shadow_get_delta", lambda t: t == "get_delta=1", 4); time.sleep(0.5); tl = toasts(page)
    rec("shadow.var_named_get_delta", "pass" if (d1 == "get_delta=1" and not tl) else "fail", f"{d1}; toasts={tl}")
    page.screenshot(path=f"{out}/shadow.png")


def counts(page) -> dict:
    t = text_of(page, "#counts")
    return json.loads(t.split("=", 1)[1])


def counts_settled(page) -> dict:
    """`counts` (cache=False) is evaluated in dirty-set order, so it may be computed before an interval var in the
    same delta; poke once more (within the 1 s interval, so nothing recomputes) and read the settled snapshot."""
    time.sleep(0.15)
    page.click("#poke"); time.sleep(0.4)
    return counts(page)


def test_interval(page, url, out):
    page.goto(f"{url}/interval")
    page.wait_for_selector("#counts")
    wait_text(page, "#ticks", lambda t: re.match(r"ticks=\d+\.\d+", t) is not None, 15)
    # A. two pokes within the interval: nothing recomputes between them
    page.click("#poke"); time.sleep(0.35)
    c0 = counts(page); t0 = text_of(page, "#ticks"); td0 = text_of(page, "#ticks_td"); m0 = text_of(page, "#mixin_ticks"); cp0 = text_of(page, "#cached_plain")
    page.click("#poke"); time.sleep(0.35)
    c1 = counts(page); t1 = text_of(page, "#ticks"); td1 = text_of(page, "#ticks_td"); m1 = text_of(page, "#mixin_ticks")
    ok = t1 == t0 and td1 == td0 and m1 == m0 and all(c1[k] == c0[k] for k in ("ticks", "ticks_td", "mixin_ticks", "cached_plain"))
    rec("interval.no_recompute_within_interval", "pass" if ok else "fail",
        f"after_poke1={c0} after_poke2(+0.35s)={c1} ticks {t0}->{t1} td {td0}->{td1} mixin {m0}->{m1}")
    # B. after expiry a poke refreshes every interval var (int, timedelta, mixin-provided) but not the plain cached var
    time.sleep(1.2)
    page.click("#poke")
    t2 = wait_text(page, "#ticks", lambda t: t != t1, 5)
    td2 = wait_text(page, "#ticks_td", lambda t: t != td1, 3); m2 = wait_text(page, "#mixin_ticks", lambda t: t != m1, 3)
    cp2 = text_of(page, "#cached_plain")
    c2 = counts_settled(page)
    d = {k: c2[k] - c1[k] for k in ("ticks", "ticks_td", "mixin_ticks", "cached_plain")}
    ok = t2 != t1 and td2 != td1 and m2 != m1 and cp2 == cp0 and d["cached_plain"] == 0 and all(1 <= d[k] <= 2 for k in ("ticks", "ticks_td", "mixin_ticks"))
    rec("interval.recompute_after_expiry_only_interval_vars", "pass" if ok else "fail",
        f"recompute deltas {d} (expect interval vars +1, cached_plain +0); ticks {t1}->{t2}; td {td1}->{td2}; mixin {m1}->{m2}; cached_plain {cp0}->{cp2}")
    # C. dependency change -> plain cached var recomputes exactly once
    page.click("#bump_base")
    cp3 = wait_text(page, "#cached_plain", lambda t: t == "cached_plain=2", 5)
    c3 = counts_settled(page)
    rec("interval.cached_var_recomputes_once_on_dep_change", "pass" if (cp3 == "cached_plain=2" and c3["cached_plain"] == c2["cached_plain"] + 1) else "fail",
        f"{cp3} cached_plain recomputes {c2['cached_plain']}->{c3['cached_plain']} (ticks {c2['ticks']}->{c3['ticks']})")
    # D. background task reading interval var through StateProxy (t0 then 1.5 s later t1)
    page.click("#clear_bg"); time.sleep(0.3)
    page.click("#bg_read_interval")
    bl = wait_text(page, "#bg_log", lambda t: "t1=" in t, 8)
    rec("interval.stateproxy_background_read", "pass" if ("t0=" in bl and "t1=" in bl and "Error" not in bl) else "fail", bl,
        note="changed=True means an expired interval var recomputes on read inside `async with self`; changed=False is also legal")
    # E. ComponentState instances (one generated class per create()) with an interval var
    ca0 = text_of(page, "#clock_a"); cb0 = text_of(page, "#clock_b")
    time.sleep(1.2); page.click("#poke"); time.sleep(0.5)
    ca1 = text_of(page, "#clock_a"); cb1 = text_of(page, "#clock_b")
    rec("interval.component_state_refresh_on_unrelated_event", "info",
        f"after 1.2 s + IntervalState.poke: clock_a changed={ca1 != ca0} clock_b changed={cb1 != cb0} ({ca0}->{ca1})")
    time.sleep(1.2); page.click("#clock_a_set")
    ca2 = wait_text(page, "#clock_a", lambda t: t != ca1, 5); time.sleep(0.3); cb2 = text_of(page, "#clock_b")
    ok = ca2 != ca1 and re.match(r"clock_a=\d+\.\d+", ca2)
    rec("interval.component_state_interval_var_refresh_on_own_event", "pass" if ok else "fail",
        f"clock_a {ca1}->{ca2}; clock_b {cb1}->{cb2} (b changed={cb2 != cb1})")
    time.sleep(1.2); page.click("#clock_b_set")
    cb3 = wait_text(page, "#clock_b", lambda t: t != cb2, 5)
    rec("interval.component_state_second_instance_refresh", "pass" if cb3 != cb2 else "fail", f"clock_b {cb2}->{cb3}")
    rec("interval.component_state_recompute_counts", "info", f"counts: {counts(page)}")
    page.screenshot(path=f"{out}/interval.png")


def test_slow(page, url, out, browser):
    page.goto(f"{url}/slow")
    page.wait_for_selector("#fast_count")
    wait_text(page, "#fast_count", lambda t: t == "fast_count=0", 15)
    page.click("#reset_slow"); time.sleep(0.3)
    # second client (separate context => separate token)
    ctx2 = browser.new_context(); p2 = ctx2.new_page(); cap2 = Capture(p2, "client2")
    p2.goto(f"{url}/slow"); p2.wait_for_selector("#fast_count")
    wait_text(p2, "#fast_count", lambda t: t == "fast_count=0", 15)

    t_start = time.time()
    page.click("#slow")
    time.sleep(0.2)
    for _ in range(3):
        page.click("#fast"); time.sleep(0.05)
    # client 2 should not be blocked
    t2 = time.time(); p2.click("#fast")
    v2 = wait_text(p2, "#fast_count", lambda t: t == "fast_count=1", 5); dt2 = time.time() - t2
    rec("slow.other_client_not_blocked", "pass" if (v2 == "fast_count=1" and dt2 < 2.0) else "fail", f"client2 fast_count after {dt2:.2f}s: {v2}")
    # same client: fast events must wait for slow (per-token ordering), then all apply in order
    mid = text_of(page, "#fast_count")
    sd = wait_text(page, "#slow_done", lambda t: t == "slow_done=1", 12)
    t_slow = time.time() - t_start
    fc = wait_text(page, "#fast_count", lambda t: t == "fast_count=3", 5)
    rec("slow.same_client_events_queued_in_order", "pass" if (mid == "fast_count=0" and sd == "slow_done=1" and fc == "fast_count=3" and 4.5 < t_slow < 9) else "fail",
        f"fast_count during slow={mid}; slow_done after {t_slow:.2f}s={sd}; then {fc}")
    # exception in handler must not wedge the socket
    page.click("#boom")
    bc = wait_text(page, "#boom_count", lambda t: t == "boom_count=1", 2.5)
    page.click("#fast")
    fc = wait_text(page, "#fast_count", lambda t: t == "fast_count=4", 5)
    rec("slow.exception_does_not_wedge_socket", "pass" if fc == "fast_count=4" else "fail", f"after boom: {bc}; then {fc}")
    rec("slow.pre_exception_mutation_delivered", "info", f"boom_count after handler raised (mutation happened before raise): {bc}")
    page.click("#boom")
    time.sleep(0.5)
    page.click("#fast")
    fc = wait_text(page, "#fast_count", lambda t: t == "fast_count=5", 5)
    bc2 = text_of(page, "#boom_count")
    rec("slow.second_exception_then_event", "pass" if fc == "fast_count=5" else "fail", f"{bc2} {fc}")
    # async handler raising before its first await (eager start: raises inside Task construction on 3.12+)
    page.click("#boom_async")
    time.sleep(0.5)
    page.click("#fast")
    fc = wait_text(page, "#fast_count", lambda t: t == "fast_count=6", 5)
    bc3 = text_of(page, "#boom_count")
    rec("slow.async_exception_before_first_await_then_event", "pass" if fc == "fast_count=6" else "fail", f"{bc3} {fc}")
    # two rapid exceptions then two rapid events
    page.evaluate("() => { for (const id of ['boom_async','boom','fast','fast']) document.getElementById(id).click(); }")
    fc = wait_text(page, "#fast_count", lambda t: t == "fast_count=8", 5)
    rec("slow.rapid_exceptions_and_events", "pass" if fc == "fast_count=8" else "fail", f"{text_of(page, '#boom_count')} {fc}")
    page.screenshot(path=f"{out}/slow_after_boom.png")
    RESULTS.append({"name": "slow.client2_capture", "status": "info", "details": json.dumps(cap2.anomalies())})
    ctx2.close()


def test_hammer(page, url, out, n=100):
    page.goto(f"{url}/")
    page.wait_for_selector("#count")
    wait_text(page, "#count", lambda t: t.startswith("count="), 15)
    page.click("#reset")
    wait_text(page, "#count", lambda t: t == "count=0", 5)
    t0 = time.time()
    for _ in range(n):
        page.click("#inc", no_wait_after=True)
    t_click = time.time() - t0
    final = wait_text(page, "#count", lambda t: t == f"count={n}", 20)
    time.sleep(0.5)
    final2 = text_of(page, "#count")
    rec("hammer.100_rapid_clicks_exact", "pass" if (final == f"count={n}" and final2 == final) else "fail",
        f"clicks took {t_click:.2f}s; final={final} (recheck {final2}); total {time.time()-t0:.2f}s")
    # JS-synchronous burst (all clicks in one tick)
    page.click("#reset"); wait_text(page, "#count", lambda t: t == "count=0", 5)
    page.evaluate("(n) => { const b = document.getElementById('inc'); for (let i=0;i<n;i++) b.click(); }", n)
    final = wait_text(page, "#count", lambda t: t == f"count={n}", 20)
    rec("hammer.100_sync_js_clicks_exact", "pass" if final == f"count={n}" else "fail", f"final={final}")
    # async handler with no await (completes eagerly on 3.12+)
    page.click("#reset"); wait_text(page, "#count", lambda t: t == "count=0", 5)
    for _ in range(n):
        page.click("#inc_async", no_wait_after=True)
    final = wait_text(page, "#count", lambda t: t == f"count={n}", 20)
    time.sleep(0.5)
    rec("hammer.100_async_noawait_clicks_exact", "pass" if (final == f"count={n}" and text_of(page, "#count") == final) else "fail", f"final={final}")
    # mixed sync/async burst
    page.click("#reset"); wait_text(page, "#count", lambda t: t == "count=0", 5)
    page.evaluate("(n) => { for (let i=0;i<n;i++) document.getElementById(i%2 ? 'inc' : 'inc_async').click(); }", n)
    final = wait_text(page, "#count", lambda t: t == f"count={n}", 20)
    rec("hammer.100_mixed_sync_async_exact", "pass" if final == f"count={n}" else "fail", f"final={final}")
    fi = text_of(page, "#factory")
    rec("hammer.factory_info", "info", fi)
    page.screenshot(path=f"{out}/hammer.png")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", default="")
    ap.add_argument("--only", default="ordering,hier,interval,backend,shadow,slow,hammer")
    a = ap.parse_args()
    Path(a.out).mkdir(parents=True, exist_ok=True)
    only = a.only.split(",")
    with sync_playwright() as pw:
        browser = launch(pw)
        ctx = browser.new_context()
        page = ctx.new_page()
        cap = Capture(page, a.label)
        for name, fn in [("ordering", test_ordering), ("hier", test_hier), ("interval", test_interval), ("backend", test_backend), ("shadow", test_shadow)]:
            if name in only:
                try:
                    fn(page, a.url, a.out)
                except Exception as e:  # noqa: BLE001
                    rec(f"{name}.EXC", "fail", f"{type(e).__name__}: {e}")
                    page.screenshot(path=f"{a.out}/{name}_exc.png")
        if "slow" in only:
            try:
                test_slow(page, a.url, a.out, browser)
            except Exception as e:  # noqa: BLE001
                rec("slow.EXC", "fail", f"{type(e).__name__}: {e}")
        if "hammer" in only:
            try:
                test_hammer(page, a.url, a.out)
            except Exception as e:  # noqa: BLE001
                rec("hammer.EXC", "fail", f"{type(e).__name__}: {e}")
        an = cap.anomalies()
        RESULTS.append({"name": "browser_capture", "status": "info", "details": json.dumps(an)})
        print("CAPTURE:", json.dumps(an, indent=1))
        dump(f"{a.out}/results.json", RESULTS)
        dump(f"{a.out}/console.json", cap.console)
        browser.close()
    fails = [r for r in RESULTS if r["status"] == "fail"]
    print(f"SUMMARY {a.label}: {len(RESULTS)} entries, {len(fails)} fail")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
