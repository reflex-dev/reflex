"""Event handler binding (#7312) on /bind."""

from __future__ import annotations


def t_bind(h):
    ctx, page = h.new_context_page("bind")
    h.goto(page, "/bind")
    page.click("#bind-clear")
    h.wait_text(page, "bind-p-log", "")
    out = {}
    for btn in ("bind-inherited-template", "bind-template-via-self", "bind-parent-via-self", "bind-bg-parent"):
        before = h.text(page, "bind-p-log")
        e0 = h.exc_count(page)
        page.click(f"#{btn}")
        page.wait_for_timeout(1500)
        out[btn] = {"p_log_added": h.text(page, "bind-p-log")[len(before):].lstrip(" ;"),
                    "p_count": h.text(page, "bind-p-count"), "c_count": h.text(page, "bind-c-count"),
                    "c_log": h.text(page, "bind-c-log"), "new_exc": h.exc_count(page) - e0,
                    "exc_tail": h.text(page, "exc-list")[-200:]}
    h.record("bind.instance_access_and_inheritance", "info", out)
    page.click("#bind-clear")
    h.wait_text(page, "bind-got", "")
    for n in range(6):
        page.click(f"#bind-take{n}-1")
        page.wait_for_timeout(250)
    page.click("#bind-lambda"); page.wait_for_timeout(250)
    page.click("#bind-rxevent-lambda"); page.wait_for_timeout(250)
    page.fill("#bind-lambda-input", "abc")
    page.click("#bind-clear", trial=True)
    page.click("text=handler binding")
    page.wait_for_timeout(800)
    got = h.text(page, "bind-got").split(" ; ")
    exp = ["take0", "take1:i1", "take2:i1:1:int", "take3:i1:1:i1", "take4:i1:1:i1:1", "take5:i1:1:i1:1:five",
           "take1:lam", "take1:rxlam", "take2:abc:5:int"]
    h.record("bind.foreach_args_0_to_5_and_lambdas", "pass" if got == exp else "fail", {"got": got, "expected": exp})
    ctx.close()


ALL = [t_bind]
