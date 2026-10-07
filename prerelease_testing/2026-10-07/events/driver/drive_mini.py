"""Driver for the `mini` app: chained-handler failure delta timing + supersedes cancel leak.

Usage: drive_mini.py BASE OUTDIR LABEL [cases]
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from harness import Harness  # noqa: E402

base, outdir, label = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
only = set(sys.argv[4].split(",")) if len(sys.argv) > 4 else None
h = Harness(base, outdir, label)

MARKERS = ["A-set", "AY-set", "B-partial", "direct-partial", "async-partial", "gen-flushed", "gen-partial",
           "onload-partial", "a:after-yield", "b:after-yield", "a:start", "b:start", "b:end", "a:end"]


def toast_visible(page) -> bool:
    return page.locator("text=An error occurred.").count() > 0


def ui(page) -> dict:
    return {k: h.text(page, k) for k in ("status", "items", "pings", "load-note", "sup-log")}


def frames_since(n0: int, tag: str) -> list[dict]:
    out = []
    for f in h.ws_frames[n0:]:
        if f["tag"] != tag or f["dir"] not in ("recv", "sent"):
            continue
        d = f["data"]
        out.append({"t": f["t"], "dir": f["dir"], "markers": [m for m in MARKERS if m in d],
                    "toast": "An error occurred" in d, "pings_in": '"pings' in d, "data": d[:500]})
    return out


def connect(tag: str, path: str = "/"):
    ctx, page = h.new_context_page(tag)
    page.goto(h.base + path, wait_until="networkidle", timeout=120000)
    page.wait_for_function("() => (document.querySelector('#version')?.textContent || '').length > 0", timeout=60000)
    return ctx, page


def roundtrip(page, expect_pings: str, timeout=10) -> bool:
    page.click("#ping")
    return h.wait_text(page, "pings", expect_pings, timeout)


def chain_case(name: str, button: str, marker_ids: dict):
    """marker_ids: element id -> substring expected from the failing handler."""
    tag = name
    ctx, page = connect(tag)
    ok0 = roundtrip(page, "1")
    n0 = len(h.ws_frames)
    t_click = h.now()
    page.click(f"#{button}")
    tl = h.timeline(page, ["status", "items"], 3.0)
    toast = toast_visible(page)
    before_ping = ui(page)
    fr1 = frames_since(n0, tag)
    n1 = len(h.ws_frames)
    t_ping = h.now()
    ok1 = roundtrip(page, "2")
    page.wait_for_timeout(500)
    after_ping = ui(page)
    fr2 = frames_since(n1, tag)
    with_error = {k: v in before_ping[k] for k, v in marker_ids.items()}
    after_next = {k: v in after_ping[k] for k, v in marker_ids.items()}
    first_marker_frame = next((f for f in fr1 + fr2 if f["dir"] == "recv" and f["markers"]), None)
    h.shot(page, name)
    # What did the server persist? Reload the tab (same token) and read the state back.
    page.reload(wait_until="networkidle")
    page.wait_for_function("() => (document.querySelector('#version')?.textContent || '').length > 0", timeout=60000)
    roundtrip(page, "3")
    page.wait_for_timeout(500)
    after_reload = ui(page)
    persisted = {k: v in after_reload[k] for k, v in marker_ids.items()}
    status = "pass" if all(with_error.values()) else ("anomaly" if all(after_next.values()) else "fail")
    h.record(f"chain.{name}", status, {
        "initial_roundtrip_ok": ok0, "ping_roundtrip_ok": ok1, "toast_visible_before_ping": toast,
        "partial_visible_with_error": with_error, "partial_visible_after_next_event": after_next,
        "partial_persisted_after_reload": persisted, "ui_after_reload": after_reload,
        "client_server_diverged": {k: after_next[k] != persisted[k] for k in marker_ids},
        "ui_before_ping": before_ping, "ui_after_ping": after_ping, "timeline": tl,
        "t_click": t_click, "t_ping": t_ping,
        "first_recv_frame_with_marker": {"t": first_marker_frame["t"], "dt_from_click": round(first_marker_frame["t"] - t_click, 3),
                                         "after_ping": first_marker_frame["t"] >= t_ping, "data": first_marker_frame["data"]} if first_marker_frame else None,
        "frames_until_ping": fr1, "frames_after_ping": fr2[:6]})
    ctx.close()


def onload_case(name: str, via_nav: bool):
    tag = name
    if via_nav:
        ctx, page = connect(tag, "/")
        roundtrip(page, "1")
        n0 = len(h.ws_frames)
        t0 = h.now()
        page.click("#to-onload")
    else:
        ctx, page = h.new_context_page(tag)
        n0 = len(h.ws_frames)
        t0 = h.now()
        page.goto(h.base + "/onload", wait_until="networkidle", timeout=120000)
    tl = h.timeline(page, ["load-note"], 3.0)
    before = ui(page)
    toast = toast_visible(page)
    fr1 = frames_since(n0, tag)
    n1 = len(h.ws_frames)
    t_ping = h.now()
    page.click("#ping")
    page.wait_for_timeout(1500)
    after = ui(page)
    fr2 = frames_since(n1, tag)
    first = next((f for f in fr1 + fr2 if f["dir"] == "recv" and "onload-partial" in f["markers"]), None)
    h.shot(page, name)
    status = "pass" if "onload-partial" in before["load-note"] else ("anomaly" if "onload-partial" in after["load-note"] else "fail")
    h.record(f"chain.{name}", status, {
        "toast_visible": toast, "load_note_before_ping": before["load-note"], "load_note_after_ping": after["load-note"],
        "timeline": tl, "t0": t0, "t_ping": t_ping,
        "first_recv_frame_with_marker": {"dt_from_start": round(first["t"] - t0, 3), "after_ping": first["t"] >= t_ping,
                                         "data": first["data"]} if first else None,
        "frames_until_ping": fr1[-8:], "frames_after_ping": fr2[:6]})
    ctx.close()


def sup_case():
    tag = "sup_cancel"
    ctx, page = connect(tag)
    roundtrip(page, "1")
    n0 = len(h.ws_frames)
    page.click("#work-a")
    page.wait_for_timeout(600)
    page.click("#work-b")
    tl = h.timeline(page, ["sup-log"], 4.5)
    final = h.text(page, "sup-log")
    fr = frames_since(n0, tag)
    leaked = "a:after-yield" in final
    first_leak = next((f for f in fr if f["dir"] == "recv" and "a:after-yield" in f["markers"]), None)
    h.record("sup.cancelled_mutation_after_last_yield", "anomaly" if leaked else "pass", {
        "final": final, "leaked_a_after_yield": leaked, "a_end_present": "a:end" in final, "timeline": tl["sup-log"],
        "first_frame_with_leak": first_leak, "frames": [f for f in fr if f["dir"] == "recv"][:8]})
    # after the run, a reload must show the same log (what was persisted)
    page.reload(wait_until="networkidle")
    page.wait_for_function("() => (document.querySelector('#version')?.textContent || '').length > 0", timeout=60000)
    roundtrip(page, "2")
    page.wait_for_timeout(500)
    h.record("sup.cancelled_mutation_after_reload", "info", {"after_reload": h.text(page, "sup-log")})
    ctx.close()


def split_case():
    """Superseding call (b) never touches `log`: does cancelled a's post-yield mutation still surface?"""
    tag = "sup_split"
    ctx, page = connect(tag)
    roundtrip(page, "1")
    n0 = len(h.ws_frames)
    page.click("#split-a")
    h.wait_pred(page, "sup-log", lambda v: "a:start" in v, 5)
    page.wait_for_timeout(600)
    page.click("#split-b")
    tl = h.timeline(page, ["sup-log", "sup-other"], 4.5)
    after_b = {"log": h.text(page, "sup-log"), "other": h.text(page, "sup-other")}
    roundtrip(page, "2")
    page.wait_for_timeout(500)
    after_ping = {"log": h.text(page, "sup-log"), "other": h.text(page, "sup-other")}
    fr = frames_since(n0, tag)
    page.reload(wait_until="networkidle")
    page.wait_for_function("() => (document.querySelector('#version')?.textContent || '').length > 0", timeout=60000)
    roundtrip(page, "3")
    page.wait_for_timeout(500)
    after_reload = {"log": h.text(page, "sup-log"), "other": h.text(page, "sup-other")}
    leak_frames = [f for f in fr if f["dir"] == "recv" and "a:after-yield" in f["data"]]
    leaked = any("a:after-yield" in x["log"] for x in (after_b, after_ping, after_reload))
    h.record("sup.split_cancelled_mutation_surfaces", "anomaly" if leaked else "pass", {
        "after_b": after_b, "after_next_event": after_ping, "after_reload": after_reload,
        "a_end_present": "a:end" in after_reload["log"], "timeline": tl,
        "first_frame_with_a_after_yield": leak_frames[0] if leak_frames else None,
        "recv_frames": [f for f in fr if f["dir"] == "recv"][:10]})
    ctx.close()


def emoji_case():
    """Prod prerender vs client text for a JS-reversed emoji (lone surrogates)."""
    out = {}
    for route in ("/emoji-plain", "/emoji-len", "/emoji-rev"):
        tag = "emoji" + route.replace("/", "_")
        e0 = len(h.page_errors)
        ctx, page = h.new_context_page(tag)
        resp = page.request.get(h.base + route + "/")
        raw = resp.body()
        page.goto(h.base + route, wait_until="networkidle", timeout=120000)
        page.wait_for_timeout(1500)
        el = route.strip("/")
        txt = h.text(page, el)
        errs = [e["error"][:200] for e in h.page_errors[e0:]]
        marker = f'id="{el}"'.encode()
        i = raw.find(marker)
        snippet = raw[i:i + 120] if i >= 0 else b""
        out[route] = {"client_text": txt, "client_codepoints": [hex(ord(c)) for c in txt], "page_errors": errs,
                      "html_status": resp.status, "html_snippet_hex": snippet.hex()[:240],
                      "html_has_replacement_char": b"\xef\xbf\xbd" in snippet}
        ctx.close()
    bad = [r for r, v in out.items() if v["page_errors"]]
    h.record("prerender.emoji_hydration", "anomaly" if bad else "pass", {"routes_with_page_errors": bad, "detail": out})


CASES = {
    "a_returns_b_raises": lambda: chain_case("a_returns_b_raises", "a-ret", {"status": "A-set", "items": "B-partial"}),
    "a_yields_b_raises": lambda: chain_case("a_yields_b_raises", "a-yield", {"status": "AY-set", "items": "B-partial"}),
    "direct_raises": lambda: chain_case("direct_raises", "direct", {"status": "direct-partial"}),
    "async_raises": lambda: chain_case("async_raises", "async", {"status": "async-partial"}),
    "gen_yield_then_raise": lambda: chain_case("gen_yield_then_raise", "gen", {"status": "gen-flushed", "items": "gen-partial"}),
    "onload_initial": lambda: onload_case("onload_initial", via_nav=False),
    "onload_via_nav": lambda: onload_case("onload_via_nav", via_nav=True),
    "sup_cancel": sup_case,
    "sup_split": split_case,
    "emoji": emoji_case,
}
try:
    for name, fn in CASES.items():
        if only and name not in only:
            continue
        print(f"--- {name}", flush=True)
        h.run(name, lambda _h, fn=fn: fn())
finally:
    p = h.dump()
    h.close()
    print("REPORT", p)
