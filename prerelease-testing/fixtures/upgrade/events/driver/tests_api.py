"""State API edge cases on /api."""

from __future__ import annotations

import json


def t_api_sibling_bg(h):
    ctx, page = h.new_context_page("api-sib")
    h.goto(page, "/api")
    x0 = int(h.text(page, "api-sib2-x"))
    page.click("#api-sib")
    rep = h.wait_pred(page, "api-sib-report", lambda v: "after=" in v, 8)
    x1 = h.wait_pred(page, "api-sib2-x", lambda v: v == str(x0 + 1), 3)
    in_lock_ok = f"in={x0} in2={x0 + 1}" in rep and x1 == str(x0 + 1)
    h.record("api.bg_get_state_get_var_value_sibling", "pass" if in_lock_ok else "fail",
             {"report": rep, "in_lock_expected": f"in={x0} in2={x0 + 1}", "ui_sibling_x": x1,
              "outside_lock_get_var_value": rep.split(" ")[0] if rep else None})
    ctx.close()


def t_api_setvar_raw(h):
    ctx, page = h.new_context_page("api-setvar")
    h.goto(page, "/api")
    results = {}
    for btn, check in [
        ("api-setvar-pub", lambda: h.wait_text(page, "api-pub", "pub-raw", 4)),
        ("api-setvar-secret", None),
        ("api-setvar-missing", None),
        ("api-setvar-computed", None),
        ("api-raw-missing-handler", None),
    ]:
        e0 = h.exc_count(page)
        page.click(f"#{btn}")
        page.wait_for_timeout(1200)
        results[btn] = {"ok": check() if check else None, "new_backend_exc": h.exc_count(page) - e0,
                        "exc_tail": h.text(page, "exc-list")[-160:], "secret_ui": h.text(page, "api-secret"),
                        "pub_ui": h.text(page, "api-pub")}
    secret_untouched = h.text(page, "api-secret") == "secret0"
    h.record("api.raw_setvar_events", "pass" if secret_untouched and results["api-setvar-pub"]["ok"] else "fail", results)
    # is_hydrated via setvar: observe the page
    e0 = h.exc_count(page)
    page.click("#api-setvar-hydrated")
    page.wait_for_timeout(1500)
    shot = h.shot(page, "setvar_is_hydrated")
    still_interactive = True
    try:
        page.click("#api-setvar-pub", timeout=3000)
    except Exception:
        still_interactive = False
    h.record("api.raw_setvar_is_hydrated_false", "info", {"new_backend_exc": h.exc_count(page) - e0,
             "exc_tail": h.text(page, "exc-list")[-200:], "still_interactive": still_interactive, "screenshot": shot})
    ctx.close()


def _storage(page):
    return page.evaluate("() => ({ls: localStorage.getItem('ev_ls'), cookie: document.cookie})")


def t_api_reset(h):
    ctx, page = h.new_context_page("api-reset")
    h.goto(page, "/api")
    ids = ["reset-ls", "reset-ck", "reset-plain", "reset-sub", "reset-cs-val"]
    before = {i: h.text(page, i) for i in ids}
    page.click("#reset-mutate")
    page.click("#reset-cs-mutate")
    h.wait_text(page, "reset-cs-val", "cs-changed", 4)
    h.wait_text(page, "reset-sub", "sub-changed", 4)
    mutated = {i: h.text(page, i) for i in ids}
    st_mut = _storage(page)
    page.click("#reset-do")
    page.wait_for_timeout(1200)
    after = {i: h.text(page, i) for i in ids}
    st_after = _storage(page)
    page.reload(wait_until="networkidle")
    h.wait_connected(page)
    page.wait_for_timeout(500)
    reloaded = {i: h.text(page, i) for i in ids}
    ok = (after["reset-ls"] == "ls-default" and after["reset-ck"] == "ck-default" and after["reset-plain"] == "plain-default"
          and after["reset-sub"] == "sub-default" and reloaded["reset-ls"] == "ls-default")
    h.record("api.reset_client_storage_substates", "pass" if ok else "fail", {
        "before": before, "mutated": mutated, "storage_mutated": st_mut, "after_reset": after,
        "storage_after_reset": st_after, "after_reload": reloaded})
    ctx.close()


def t_api_dataclass(h):
    ctx, page = h.new_context_page("api-dc")
    h.goto(page, "/api")
    i0, n0 = h.text(page, "dc-items"), h.text(page, "dc-nested")
    page.click("#dc-mutate")
    h.wait_pred(page, "dc-items", lambda v: v != i0, 4)
    page.click("#dc-mutate")
    page.wait_for_timeout(800)
    i1, n1 = h.text(page, "dc-items"), h.text(page, "dc-nested")
    page.click("#dc-snapshot")
    snap = h.wait_pred(page, "dc-snap", lambda v: v.startswith("{"), 4)
    try:
        snapj = json.loads(snap)
    except Exception:
        snapj = snap
    ctx2, page2 = h.new_context_page("api-dc-2")
    h.goto(page2, "/api")
    other = (h.text(page2, "dc-items"), h.text(page2, "dc-nested"))
    ok = i1 == "[0,1]" and n1 == "[[1,7,7]]" and other == ("[]", "[[1]]") and isinstance(snapj, dict) and snapj.get("gv", {}).get("items") == [0, 1]
    h.record("api.dataclass_nested_inplace_mutation", "pass" if ok else "fail", {
        "initial": [i0, n0], "after_2_mutations": [i1, n1], "snapshot": snapj, "other_session": other})
    ctx2.close()
    ctx.close()


def t_api_undeclared(h):
    ctx, page = h.new_context_page("api-undecl")
    h.goto(page, "/api")
    e0 = h.exc_count(page)
    frames0 = len(h.ws_frames)
    page.click("#undecl-assign")
    page.wait_for_timeout(1500)
    rep1 = h.text(page, "undecl-report")
    dexc = h.exc_count(page) - e0
    leaked_in_delta = any(('undeclared_attr\\":' in f["data"] or 'undeclared_attr":' in f["data"]) for f in h.ws_frames[frames0:] if f["dir"] == "recv")
    page.click("#undecl-read")
    page.wait_for_timeout(1200)
    rep2 = h.text(page, "undecl-report")
    h.record("api.undeclared_attribute_assignment", "info", {
        "report_after_assign": rep1, "backend_exc": dexc, "exc_tail": h.text(page, "exc-list")[-200:],
        "report_after_readback": rep2, "undeclared_name_in_ws_delta": leaked_in_delta})
    ctx.close()


ALL = [t_api_sibling_bg, t_api_setvar_raw, t_api_reset, t_api_dataclass, t_api_undeclared]
