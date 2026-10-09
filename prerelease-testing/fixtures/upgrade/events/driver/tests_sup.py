"""Supersedes / background / decorator-order tests (pages /sup and /deco)."""

from __future__ import annotations

import time


def _clear_sup(h, page):
    page.click("#sup-clear")
    h.wait_text(page, "slow-log", "")
    for n in ("A", "B"):
        page.click(f"#cs-clear-{n}")
    page.wait_for_timeout(300)


def t_sup_slow(h):
    ctx, page = h.new_context_page("sup-slow")
    h.goto(page, "/sup")
    _clear_sup(h, page)
    t0 = time.time()
    page.click("#slow-a"); page.wait_for_timeout(300)
    page.click("#slow-b"); page.wait_for_timeout(300)
    page.click("#slow-c")
    tl = h.timeline(page, ["slow-log"], 7.5)
    final = h.text(page, "slow-log")
    exp = "a0,b0,c0,c1,c2,c3,c4,cdone"
    h.record("sup.slow_rapid_clicks", "pass" if final == exp else "fail", {"final": final, "expected": exp, "timeline": tl["slow-log"]})
    ctx.close()


def t_sup_partial(h):
    ctx, page = h.new_context_page("sup-partial")
    h.goto(page, "/sup")
    _clear_sup(h, page)
    page.click("#partial-a"); page.wait_for_timeout(600)
    page.click("#partial-b")
    tl = h.timeline(page, ["partial-log"], 4.5)
    final = h.text(page, "partial-log")
    leaked = "aunflushed" in final
    h.record("sup.cancelled_unyielded_mutation", "anomaly" if leaked else "pass",
             {"final": final, "cancelled_handler_mutation_after_last_yield_visible": leaked, "timeline": tl["partial-log"]})
    ctx.close()


def t_sup_bg(h):
    ctx, page = h.new_context_page("sup-bg")
    h.goto(page, "/sup")
    _clear_sup(h, page)
    page.click("#bg-a"); page.wait_for_timeout(300)
    page.click("#bg-b"); page.wait_for_timeout(300)
    page.click("#bg-c")
    tl = h.timeline(page, ["bg-log"], 7.5)
    final = h.text(page, "bg-log")
    exp = "a0,b0,c0,c1,c2,c3,c4,cdone"
    h.record("sup.background_plus_supersedes", "pass" if final == exp else "fail", {"final": final, "expected": exp, "timeline": tl["bg-log"]})
    ctx.close()


def t_sup_lock(h):
    ctx, page = h.new_context_page("sup-lock")
    h.goto(page, "/sup")
    _clear_sup(h, page)
    page.click("#lock-a"); page.wait_for_timeout(600)
    page.click("#lock-b"); page.wait_for_timeout(300)
    page.click("#ping-1")
    tl = h.timeline(page, ["lock-log"], 5)
    page.click("#ping-2")
    ok = h.wait_pred(page, "lock-log", lambda v: "ping-2" in v, 8)
    final = h.text(page, "lock-log")
    status = "pass" if ("bdone" in final and "ping-2" in final and "ain2" not in final) else "fail"
    h.record("sup.bg_cancel_while_holding_lock", status, {"final": final, "a_in_kept": "ain" in final, "timeline": tl["lock-log"]})
    ctx.close()


def t_sup_cpu(h):
    ctx, page = h.new_context_page("sup-cpu")
    h.goto(page, "/sup")
    _clear_sup(h, page)
    page.click("#cpu-a"); page.wait_for_timeout(100)
    page.click("#cpu-b"); page.wait_for_timeout(100)
    page.click("#cpu-c")
    tl = h.timeline(page, ["cpu-log"], 7)
    final = h.text(page, "cpu-log")
    h.record("sup.cpu_bound_non_yielding", "info", {"final": final, "timeline": tl["cpu-log"]})
    ctx.close()


def t_sup_gen(h):
    ctx, page = h.new_context_page("sup-gen")
    h.goto(page, "/sup")
    _clear_sup(h, page)
    page.click("#gen-a"); page.wait_for_timeout(300)
    page.click("#gen-b")
    tl = h.timeline(page, ["gen-log"], 5)
    final = h.text(page, "gen-log")
    h.record("sup.sync_generator_blocking_sleep", "info", {"final": final, "timeline": tl["gen-log"]})
    ctx.close()


def t_sup_chain(h):
    ctx, page = h.new_context_page("sup-chain")
    h.goto(page, "/sup")
    _clear_sup(h, page)
    page.click("#chain-a"); page.wait_for_timeout(1600)
    t_click = time.time()
    page.click("#chain-b")
    tl = h.timeline(page, ["chain-log", "slow-log"], 6.5)
    final = h.text(page, "chain-log")
    b0_at = next((t for t, v in tl["chain-log"] if "b0" in v), None)
    child_a_cancelled = "adone" not in final and "a3" not in final
    status = "pass" if child_a_cancelled and final.endswith("b0,b1,b2,b3,bdone") else "fail"
    h.record("sup.chained_child_cancelled", status, {"final": final, "parent_log": h.text(page, "slow-log"),
             "b0_seconds_after_click": b0_at, "child_a_cancelled": child_a_cancelled, "timeline": tl["chain-log"]})
    ctx.close()


def t_sup_component_state(h):
    ctx, page = h.new_context_page("sup-cs")
    h.goto(page, "/sup")
    _clear_sup(h, page)
    page.click("#cs-run-A"); page.wait_for_timeout(300)
    page.click("#cs-run-B")
    tl = h.timeline(page, ["cs-log-A", "cs-log-B"], 8)
    fa, fb = h.text(page, "cs-log-A"), h.text(page, "cs-log-B")
    status = "pass" if (fa == "A0,A1,A2,Adone" and fb == "B0,B1,B2,Bdone") else "fail"
    h.record("sup.component_state_instances_independent", status, {"A": fa, "B": fb, "timeline": tl})
    page.click("#cs-clear-A"); h.wait_text(page, "cs-log-A", "")
    page.click("#cs-run-A"); page.wait_for_timeout(400)
    page.click("#cs-run-A")
    h.timeline(page, ["cs-log-A"], 5)
    fa2 = h.text(page, "cs-log-A")
    h.record("sup.component_state_self_supersede", "pass" if fa2 == "A0,A0,A1,A2,Adone" else "fail", {"A": fa2, "expected": "A0,A0,A1,A2,Adone"})
    ctx.close()


def _deco_case(h, page, button, expect_start, expect_end, ping="#deco-ping1", ping_label="ping1", wait=3.0):
    page.click("#deco-clear")
    h.wait_text(page, "deco-log", "")
    exc0 = h.exc_count(page)
    page.click(button)
    page.wait_for_timeout(250)
    page.click(ping)
    tl = h.timeline(page, ["deco-log"], wait)
    final = h.text(page, "deco-log")
    concurrent = final == f"{expect_start},{ping_label},{expect_end}"
    return final, concurrent, h.exc_count(page) - exc0, tl["deco-log"]


def t_deco(h):
    ctx, page = h.new_context_page("deco")
    h.goto(page, "/deco")
    for name, btn, s, e in [
        ("late_marker_before_first_use", "#deco-late", "late:start", "late:end"),
        ("late_marker_after_is_background_read", "#deco-lateread", "lateread:start", "lateread:end"),
        ("functools_wraps_inner", "#deco-wrapinner", "wrapinner:start", "wrapinner:end"),
        ("functools_wraps_outer", "#deco-wrapouter", "wrapouter:start", "wrapouter:end"),
    ]:
        final, conc, dexc, tl = _deco_case(h, page, btn, s, e)
        errs = h.text(page, "exc-list")
        h.record(f"deco.{name}", "pass" if conc and dexc == 0 else "fail",
                 {"final": final, "ran_as_background": conc, "new_backend_errors": dexc, "exc_list_tail": errs[-300:], "timeline": tl})
    page.click("#deco-trace")
    h.wait_pred(page, "deco-log", lambda v: "trace=" in v, 5)
    h.record("deco.trace_wrapper_executed", "info", {"log": h.text(page, "deco-log")})
    # mixin inherited by two substates, both background
    page.click("#mix-a"); page.wait_for_timeout(150)
    page.click("#mix-b"); page.wait_for_timeout(150)
    page.click("#mix-a-ping")
    tl = h.timeline(page, ["mix-a-log", "mix-b-log"], 3)
    a, b = h.text(page, "mix-a-log"), h.text(page, "mix-b-log")
    ok = a == "A:start,pingA,A:end" and b == "B:start,B:end"
    b_started_before_a_end = any("B:start" in v for t, v in tl["mix-b-log"] if t < next((t2 for t2, v2 in tl["mix-a-log"] if "A:end" in v2), 99))
    h.record("deco.mixin_background_two_substates", "pass" if ok and b_started_before_a_end else "fail",
             {"A": a, "B": b, "B_started_before_A_end": b_started_before_a_end, "timeline": tl})
    # package handler re-decorated with rx.event(fn, background=True) after a component referenced it
    for btn in ("#pkg-early", "#pkg-late"):
        before = h.text(page, "pkg-log")
        exc0 = h.exc_count(page)
        page.click(btn); page.wait_for_timeout(250)
        page.click("#pkg-ping")
        h.timeline(page, ["pkg-log"], 2.6)
        after = h.text(page, "pkg-log")
        added = after[len(before):].lstrip(",")
        h.record(f"deco.pkg_redecorated_{btn[5:]}", "pass" if added == "pkg:start,ping,pkg:end" and h.exc_count(page) == exc0 else "fail",
                 {"added": added, "new_backend_errors": h.exc_count(page) - exc0})
    h.shot(page, "deco")
    ctx.close()


ALL = [t_sup_slow, t_sup_partial, t_sup_bg, t_sup_lock, t_sup_cpu, t_sup_gen, t_sup_chain, t_sup_component_state, t_deco]
