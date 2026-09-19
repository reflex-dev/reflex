"""Drive routerlab and record which rx_router_* vars land in each delta.

Usage:
  $SB/envs/driver/bin/python drive_router.py <base_url> <out_prefix> [--legacy]

--legacy: the app is running on 0.9.11.post1 (single `router` var) - report that key instead.
"""

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1]
OUT = Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
LEGACY = "--legacy" in sys.argv

console_msgs = []
page_errors = []
bad_responses = []
ws_frames = []  # (label, direction, payload)
CURRENT = {"label": "boot"}


def router_keys(delta_payload):
    """Extract per-state router-ish keys + byte size from a delta frame."""
    out = {}
    for state_name, fields in delta_payload.items():
        keys = [k for k in fields if k.startswith("rx_router_") or k == "router"]
        if keys:
            out[state_name] = sorted(keys)
    return out


def on_ws(ws):
    def rx(payload):
        ws_frames.append((CURRENT["label"], "recv", payload))

    def tx(payload):
        ws_frames.append((CURRENT["label"], "sent", payload))

    ws.on("framereceived", rx)
    ws.on("framesent", tx)


def decode(payload):
    """socket.io frames look like 42["event",{...}]; return list of json objects."""
    if isinstance(payload, bytes):
        try:
            payload = payload.decode("utf8", "replace")
        except Exception:
            return None
    i = payload.find("[")
    if i < 0:
        return None
    try:
        return json.loads(payload[i:])
    except Exception:
        return None


def snapshot(page):
    ids = [
        "page_title", "cv_auto_path", "cv_deps_whole_router", "cv_deps_router_url",
        "cv_deps_legacy_string", "cv_headers", "cv_session", "cv_page_params",
        "cv_query_params", "cv_route_id", "cv_frag", "sub_cv", "sub_note",
        "counter", "direct_token", "direct_path", "direct_rid", "cond_out",
        "match_out", "memo_path", "cs_path", "cs_clicks", "cs_value",
        "item_loaded_id", "search_q",
    ]
    res = {}
    for i in ids:
        try:
            el = page.query_selector(f"#{i}")
            res[i] = el.inner_text() if el else None
        except Exception as e:
            res[i] = f"<err {e}>"
    try:
        wr = page.query_selector("#whole_router")
        res["whole_router"] = (wr.inner_text()[:400] if wr else None)
    except Exception:
        pass
    return res


def step(page, label, fn, settle=1.2):
    CURRENT["label"] = label
    before = len(ws_frames)
    fn()
    # page.wait_for_timeout pumps the playwright event loop; time.sleep does NOT,
    # so websocket frames would otherwise only be delivered during the next call.
    page.wait_for_timeout(int(settle * 1000))
    page.wait_for_timeout(200)
    frames = ws_frames[before:]
    recv = []
    for lab, direction, payload in frames:
        if direction != "recv":
            continue
        obj = decode(payload)
        if not obj or not isinstance(obj, list) or len(obj) < 2:
            continue
        if obj[0] != "event":
            continue
        body = obj[1]
        delta = body.get("delta") if isinstance(body, dict) else None
        if delta is None:
            continue
        recv.append({
            "bytes": len(payload if isinstance(payload, str) else payload),
            "router_keys": router_keys(delta),
            "all_states": {k: sorted(v.keys()) for k, v in delta.items()},
        })
    snap = snapshot(page)
    record = {"label": label, "url": page.url, "deltas": recv, "snapshot": snap}
    print(f"\n=== {label} ===  url={page.url}")
    for d in recv:
        print(f"   delta {d['bytes']}B router_keys={d['router_keys']}")
        print(f"        all={d['all_states']}")
    for k in ("cv_auto_path", "cv_deps_whole_router", "cv_deps_router_url",
              "cv_deps_legacy_string", "cv_query_params", "cv_route_id",
              "cv_page_params", "cv_frag", "sub_cv", "cond_out", "match_out",
              "memo_path", "cs_path", "direct_path", "direct_rid"):
        if snap.get(k):
            print(f"        {k}: {snap[k]}")
    return record


records = []

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = browser.new_context(extra_http_headers={"x-rxtest": "CTX-ONE"})
    page = ctx.new_page()
    page.on("console", lambda m: console_msgs.append((CURRENT["label"], m.type, m.text[:400])))
    page.on("pageerror", lambda e: page_errors.append((CURRENT["label"], str(e)[:400])))
    page.on("response", lambda r: bad_responses.append((CURRENT["label"], r.status, r.url)) if r.status >= 400 else None)
    page.on("websocket", on_ws)

    records.append(step(page, "01_initial_load_home", lambda: page.goto(f"{BASE}/", wait_until="networkidle"), settle=2.5))
    page.screenshot(path=str(OUT / "01_home.png"))

    records.append(step(page, "02_event_no_route_change(bump)", lambda: page.click("#btn_bump")))
    records.append(step(page, "03_clientside_nav_to_/items/1", lambda: page.click("#nav_item1"), settle=1.6))
    page.screenshot(path=str(OUT / "03_item1.png"))
    records.append(step(page, "04_same_route_diff_id_/items/2", lambda: page.click("#nav_item2"), settle=1.6))
    records.append(step(page, "05_nav_to_/docs/a/b_catchall", lambda: page.click("#nav_docs"), settle=1.6))
    records.append(step(page, "06_nav_to_/search?q=hello", lambda: page.click("#nav_search"), settle=1.6))
    page.screenshot(path=str(OUT / "06_search.png"))
    records.append(step(page, "07_substate_handler_read_router", lambda: page.click("#btn_subread")))
    records.append(step(page, "08_background_task_read_router", lambda: page.click("#btn_bg"), settle=1.6))
    records.append(step(page, "09_componentstate_click", lambda: page.click("#cs_btn")))
    records.append(step(page, "10_client_state_set_from_router", lambda: page.click("#btn_cs")))
    records.append(step(page, "11_back", lambda: page.go_back(), settle=1.8))
    records.append(step(page, "12_forward", lambda: page.go_forward(), settle=1.8))
    records.append(step(page, "13_reload_on_search", lambda: page.reload(wait_until="networkidle"), settle=2.2))
    records.append(step(page, "14_mutate_headers_handler", lambda: page.click("#btn_mutate")))
    records.append(step(page, "15_bump_after_header_mutation", lambda: page.click("#btn_bump")))
    records.append(step(page, "16_direct_load_/items/7?x=1#frag",
                        lambda: page.goto(f"{BASE}/items/7?x=1#frag", wait_until="networkidle"), settle=2.5))
    page.screenshot(path=str(OUT / "16_item7.png"))
    records.append(step(page, "17_event_chain_redirect", lambda: page.click("#btn_chain"), settle=2.0))
    records.append(step(page, "18_redirect_about", lambda: page.click("#btn_redirect"), settle=2.0))
    records.append(step(page, "19_onload_redirect_/items/redirectme",
                        lambda: page.goto(f"{BASE}/items/redirectme", wait_until="networkidle"), settle=2.5))
    page.screenshot(path=str(OUT / "19_redirectme.png"))

    # second tab in SAME context (same token? separate token per tab)
    CURRENT["label"] = "20_second_tab"
    page2 = ctx.new_page()
    page2.on("websocket", on_ws)
    page2.on("console", lambda m: console_msgs.append(("20_second_tab", m.type, m.text[:400])))
    page2.on("pageerror", lambda e: page_errors.append(("20_second_tab", str(e)[:400])))
    records.append(step(page2, "20_second_tab_load_/items/99",
                        lambda: page2.goto(f"{BASE}/items/99", wait_until="networkidle"), settle=2.5))
    records.append(step(page2, "21_second_tab_nav_/about", lambda: page2.click("#nav_about"), settle=1.6))
    page2.screenshot(path=str(OUT / "21_tab2.png"))
    page2.close()

    # SECOND CONTEXT with a different custom header
    CURRENT["label"] = "22_second_context"
    ctx2 = browser.new_context(extra_http_headers={"x-rxtest": "CTX-TWO"})
    p3 = ctx2.new_page()
    p3.on("websocket", on_ws)
    p3.on("console", lambda m: console_msgs.append(("22_second_context", m.type, m.text[:400])))
    p3.on("pageerror", lambda e: page_errors.append(("22_second_context", str(e)[:400])))
    records.append(step(p3, "22_second_context_load_home",
                        lambda: p3.goto(f"{BASE}/", wait_until="networkidle"), settle=2.5))
    records.append(step(p3, "23_second_context_nav_item1", lambda: p3.click("#nav_item1"), settle=1.6))
    p3.screenshot(path=str(OUT / "23_ctx2.png"))
    ctx2.close()

    # back on page 1: one more event to confirm session var stability
    records.append(step(page, "24_final_bump", lambda: page.click("#btn_bump")))
    page.screenshot(path=str(OUT / "24_final.png"))

    browser.close()

(OUT / "records.json").write_text(json.dumps(records, indent=1))
(OUT / "ws_frames.txt").write_text(
    "\n".join(f"[{lab}] {d}: {(pl if isinstance(pl,str) else repr(pl))[:3000]}" for lab, d, pl in ws_frames)
)
print("\n\n================ CONSOLE ================")
for lab, t, txt in console_msgs:
    if t in ("error", "warning") or "error" in txt.lower() or "warn" in txt.lower():
        print(f"[{lab}] {t}: {txt}")
print(f"(total console msgs: {len(console_msgs)})")
print("================ PAGE ERRORS ================")
for lab, e in page_errors:
    print(f"[{lab}] {e}")
print("================ BAD RESPONSES ================")
for lab, s, u in bad_responses:
    print(f"[{lab}] {s} {u}")
print("DONE")
