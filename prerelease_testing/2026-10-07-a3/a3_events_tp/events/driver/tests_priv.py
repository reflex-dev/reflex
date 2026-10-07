"""#7465: double-underscore private attributes inside event handlers (page /priv)."""

from __future__ import annotations


def _recv_since(h, n0, tag):
    return [f["data"] for f in h.ws_frames[n0:] if f["tag"] == tag and f["dir"] == "recv"]


def t_priv(h):
    tag = "priv"
    ctx, page = h.new_context_page(tag)
    h.goto(page, "/priv")
    alpha = h.text(page, "reflex-version").startswith("0.10")
    e0 = h.exc_count(page)
    steps = {}
    for i in range(4):
        page.click("#priv-bump")
        page.wait_for_timeout(350)
    h.wait_pred(page, "priv-count", lambda v: v == "3", 5)
    steps["after_4_bumps"] = {"count": h.text(page, "priv-count"), "note": h.text(page, "priv-note"), "view": h.text(page, "priv-view")}
    n0 = len(h.ws_frames)
    page.click("#priv-only")
    page.wait_for_timeout(1200)
    frames = _recv_since(h, n0, tag)
    steps["private_only"] = {
        "note": h.text(page, "priv-note"), "view": h.text(page, "priv-view"),
        "recv_frames": len(frames), "frames_mention_last_seen": any("last_seen" in f for f in frames),
        "frames_mention_privA_delta": any("priv_a" in f.lower() for f in frames),
        "frames": [f[:300] for f in frames][:4],
    }
    page.click("#priv-read")
    steps["readback"] = h.wait_pred(page, "priv-note", lambda v: v.startswith("readback"), 5)
    steps["view_after_readback"] = h.text(page, "priv-view")
    page.click("#priv-mixa"); page.wait_for_timeout(400)
    page.click("#priv-mixb"); page.wait_for_timeout(400)
    steps["mix_out_after_scratch"] = [h.text(page, "priv-mixa-out"), h.text(page, "priv-mixb-out")]
    page.click("#priv-mixa-read"); page.wait_for_timeout(400)
    page.click("#priv-mixb-read"); page.wait_for_timeout(600)
    steps["mix_out_after_read"] = [h.text(page, "priv-mixa-out"), h.text(page, "priv-mixb-out")]
    if alpha and page.locator("#privf-inc").count():
        page.click("#privf-inc"); page.wait_for_timeout(300)
        page.click("#privf-inc")
        steps["field_dunder_view"] = h.wait_pred(page, "privf-view", lambda v: v == "2", 5)
    steps["new_backend_exc"] = h.exc_count(page) - e0
    steps["exc_list"] = h.text(page, "exc-list")[-400:]
    page.reload(wait_until="networkidle")
    h.wait_connected(page)
    page.wait_for_timeout(500)
    steps["after_reload"] = {"count": h.text(page, "priv-count"), "note": h.text(page, "priv-note"),
                             "view": h.text(page, "priv-view"), "mixA": h.text(page, "priv-mixa-out")}
    h.shot(page, "priv")
    ok = (steps["after_4_bumps"]["count"] == "3"
          and steps["after_4_bumps"]["note"] == "count=3 last=3 limit=3 ver=v1"
          and not steps["private_only"]["frames_mention_last_seen"]
          and steps["readback"] == "readback last=P"
          and steps["mix_out_after_scratch"] == ["scratch=SA limit=2", "scratch=SB limit=2"]
          and steps["mix_out_after_read"] == ["read=SA", "read=SB"]
          and steps.get("field_dunder_view", "2") == "2"
          and steps["new_backend_exc"] == 0)
    h.record("priv.dunder_attrs_in_handlers", "pass" if ok else "fail", steps)
    ctx.close()


ALL = [t_priv]
