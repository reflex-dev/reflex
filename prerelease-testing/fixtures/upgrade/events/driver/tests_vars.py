"""Var operation checks on /vars, compared against Python semantics."""

from __future__ import annotations

ITEMS = list(range(10))
S = "abcdefghij"
EMOJI = "a\U0001f600b"
D = {"x": 1, "y": 2, "z": 3}
ROWS = ["b", "a", "c"]


def js_list(v):
    return "[" + ",".join(str(x) for x in v) + "]"


def expected(step, a, b, key, alpha):
    e = {
        "v-rev-foreach": [str(x) for x in ITEMS[-1::-1]],
        "v-ab-foreach": [str(x) for x in ITEMS[a:b]],
        "v-s-rev2": S[::-2],
        "v-s-ab": S[a:b],
        "v-emoji-rev": EMOJI[::-1],
        "v-emoji-len": str(len(EMOJI)),
        "v-ab-str": js_list(ITEMS[a:b]),
        "v-objkey": str(D[key]) if key in D else "",
        "v-dict-foreach": [f"{k}={v}" for k, v in D.items()],
        "v-dict-items": [f"{k}:{v}" for k, v in D.items()],
        "v-pluck": ",".join(ROWS),
        "v-pluck-rev": ",".join(reversed(ROWS)),
        "v-rev-slice": js_list(list(reversed(ITEMS))[0:3]),
    }
    if alpha:
        e.update({
            "v-step-foreach": [str(x) for x in ITEMS[::step]],
            "v-ba-rev-foreach": [str(x) for x in ITEMS[b:a:-1]],
            "v-s-step": S[::step],
            "v-step-len": str(len(ITEMS[::step])),
            "v-step-contains": "has4" if 4 in ITEMS[::step] else "no4",
            "v-abs-str": js_list(ITEMS[a:b:step]),
            "v-hook": "hook-ok",
        })
    return e


def read(h, page, keys):
    out = {}
    for k in keys:
        if k.endswith("foreach") or k == "v-dict-items":
            out[k] = h.spans(page, k)
        else:
            out[k] = h.text(page, k)
    return out


def check(h, page, name, step, a, b, key, alpha):
    page.wait_for_timeout(700)
    exp = expected(step, a, b, key, alpha)
    got = read(h, page, exp.keys())
    bad = {k: {"got": got[k], "exp": exp[k]} for k in exp if got[k] != exp[k]}
    known = {"v-emoji-rev", "v-emoji-len"}
    real_bad = {k: v for k, v in bad.items() if k not in known}
    h.record(f"vars.{name}", "pass" if not real_bad else "fail", {"mismatches": real_bad, "checked": len(exp)})
    if bad.keys() & known:
        h.record(f"vars.{name}.utf16_vs_codepoints", "anomaly", {k: bad[k] for k in bad.keys() & known})


def t_vars(h):
    ctx, page = h.new_context_page("vars")
    h.goto(page, "/vars")
    alpha = h.text(page, "reflex-version").startswith("0.10")
    check(h, page, "initial", 2, 2, 7, "y", alpha)
    page.click("#v-step-neg3")
    check(h, page, "step_neg3", -3, 2, 7, "y", alpha)
    page.click("#v-bounds-72")
    check(h, page, "bounds_7_2_step_neg3", -3, 7, 2, "y", alpha)
    page.click("#v-step-2")
    page.click("#v-bounds-neg")
    check(h, page, "bounds_neg8_neg2_step2", 2, -8, -2, "y", alpha)
    page.click("#v-step-neg3")
    check(h, page, "bounds_neg8_neg2_step_neg3", -3, -8, -2, "y", alpha)
    page.click("#v-key-z")
    check(h, page, "objkey_z", -3, -8, -2, "z", alpha)
    page.click("#v-key-missing")
    check(h, page, "objkey_missing", -3, -8, -2, "missing", alpha)
    page.click("#v-step-2"); page.click("#v-bounds-27")
    if alpha:
        de = {k: h.text(page, k) for k in ("v-deq-cs", "v-deq-comp", "v-deq-match")}
        ok1 = de == {"v-deq-cs": "eq", "v-deq-comp": "eq", "v-deq-match": "M-eq"}
        page.click("#v-mutate-left")
        page.wait_for_timeout(800)
        de2 = {k: h.text(page, k) for k in ("v-deq-cs", "v-deq-comp", "v-deq-match", "v-left")}
        ok2 = de2["v-deq-cs"] == "neq" and de2["v-deq-comp"] == "eq" and de2["v-deq-match"] == "M-neq"
        page.click("#v-cs-set")
        page.wait_for_timeout(800)
        de3 = {k: h.text(page, k) for k in ("v-deq-cs", "v-csdict")}
        ok3 = de3["v-deq-cs"] == "eq"
        h.record("vars.deep_equals_state_client_computed_cond_match", "pass" if ok1 and ok2 and ok3 else "fail",
                 {"initial": de, "after_mutate_left": de2, "after_client_set": de3})
    h.shot(page, "vars")
    ctx.close()


ALL = [t_vars]
