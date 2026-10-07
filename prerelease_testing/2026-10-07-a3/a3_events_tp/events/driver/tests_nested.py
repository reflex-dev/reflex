"""Nested event list tests (#7319) on /nested. Each case uses a fresh page so a wedged
client queue (the 0.9.12 bug) cannot leak into the next case."""

from __future__ import annotations


def _fresh(h, tag):
    ctx, page = h.new_context_page(tag)
    h.goto(page, "/nested")
    page.click("#nest-clear")
    h.wait_text(page, "nest-order", "")
    h.wait_text(page, "exc-count", "0")
    return ctx, page


def _then_ordinary(h, page):
    """After the case, an ordinary event must still dispatch (queue not wedged)."""
    before = h.text(page, "nest-order")
    page.click("#nest-ordinary")
    after = h.wait_pred(page, "nest-order", lambda v: v.endswith("O") and v != before, 5)
    return after.endswith("O") and after != before


def _case(h, name, *args, **kwargs):
    try:
        _case_inner(h, name, *args, **kwargs)
    except Exception as e:  # a crashed renderer (0.9.12 error storm) must not abort the other cases
        storm = {k: v for k, v in h.counters.items() if k.startswith(f"console:{name}:") or k.startswith(f"pageerror:{name}") or k.startswith(f"ws:{name}:sent")}
        h.record(f"nested.{name}", "fail", {"exception": f"{type(e).__name__}: {str(e)[:200]}", "capture_counters": storm})


def _case_inner(h, name, button, expected_order, expected_exc=0, wait=2.5, expect_frontend_exc=None):
    ctx, page = _fresh(h, name)
    fe0 = h.counts(page)
    page.click(f"#{button}")
    page.wait_for_timeout(int(wait * 1000))
    order = h.text(page, "nest-order")
    exc = h.exc_count(page)
    ordinary_ok = _then_ordinary(h, page)
    counts = h.counts(page)
    ok = order == expected_order and exc == expected_exc and ordinary_ok
    storm = {k: v for k, v in h.counters.items() if k.startswith(f"console:{name}:") or k.startswith(f"pageerror:{name}") or k.startswith(f"ws:{name}:sent")}
    h.record(f"nested.{name}", "pass" if ok else "fail", {"capture_counters": storm,
        "order": order, "expected": expected_order, "backend_exc_records": exc, "expected_exc": expected_exc,
        "ordinary_after_ok": ordinary_ok, "exc_list": h.text(page, "exc-list")[:300],
        "handler_counts_before": fe0, "handler_counts_after": counts})
    ctx.close()


def t_nested_cases(h):
    _case(h, "match_list_branch", "nest-match", "M1,M2")
    _case(h, "deep50_nested_match", "nest-deep50", ",".join(f"Z{i}" for i in range(49, -1, -1)), wait=4)
    _case(h, "backend_failure_mid_list_flat", "nest-boom-flat", "P1,P2,P3", expected_exc=1)
    _case(h, "backend_failure_mid_nested_list", "nest-boom-match", "Q1,Q2", expected_exc=1)
    _case(h, "malformed_event_mid_nested_list", "nest-malformed", "W1,W2")
    _case(h, "handler_returns_nested_list", "nest-ret", "A,B,C,D")
    _case(h, "handler_yields_nested_list", "nest-yield", "Y1,Y2")
    _case(h, "handler_returns_flat_with_failing", "nest-ret-boom", "R1,R2", expected_exc=1)
    _case(h, "call_script_throws_mid_nested_list", "nest-cs-throw", "C1,C2")
    _case(h, "call_script_callback_list", "nest-cs-cb", "cbv,CB2")
    _case(h, "run_script_mid_nested_list", "nest-rs", "RS1,RS2")


def t_nested_prevent_default(h):
    ctx, page = _fresh(h, "pd")
    page.click("#pd-input")
    page.keyboard.type("xyx")
    page.wait_for_timeout(1500)
    val = page.input_value("#pd-input")
    order = h.text(page, "nest-order")
    ok = val == "y" and order == "PDX,PDX2,PDX,PDX2"
    ordinary_ok = _then_ordinary(h, page)
    h.record("nested.prevent_default_inside_nested_list", "pass" if ok and ordinary_ok else "fail",
             {"input_value": val, "expected_value": "y", "order": order, "ordinary_after_ok": ordinary_ok})
    ctx.close()


def t_nested_ctrl_b(h):
    ctx, page = _fresh(h, "ctrlb")
    page.click("text=nested event lists")
    page.keyboard.press("Control+b")
    page.wait_for_timeout(1500)
    order = h.text(page, "nest-order")
    ordinary_ok = _then_ordinary(h, page)
    h.record("nested.issue7319_ctrl_b_shortcut", "pass" if order == "K1,K2" and ordinary_ok else "fail",
             {"order": order, "ordinary_after_ok": ordinary_ok})
    ctx.close()


ALL = [t_nested_cases, t_nested_prevent_default, t_nested_ctrl_b]
