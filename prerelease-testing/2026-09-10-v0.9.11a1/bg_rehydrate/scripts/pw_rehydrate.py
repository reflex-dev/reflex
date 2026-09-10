"""Drive rehydrate_app in Chromium: #7073 (backend-initiated event on expired state) and
#7072 (post-eviction rehydrate fallback) plus adjacent scenarios.

Usage: NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python pw_rehydrate.py \
   --url http://localhost:3221 --api http://localhost:8221 --exp 5 --out logs/pw_rehydrate_smoke_redis \
   --shots shots/rehydrate_smoke_redis --label smoke_redis [--skip unknown_token]
"""
from __future__ import annotations

import argparse
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from playwright.sync_api import sync_playwright  # noqa: E402
from pwlib import RESULTS, Capture, dump, hydrate_deltas, http_json, launch, rec, snapshot, text_of, token_of, wait_text  # noqa: E402

IDS = ["title", "hydrated", "path", "loaded_page", "load_seq", "loaded_at", "clicks", "pings", "bg_status", "name", "flavor", "other_count", "item_arg"]
ROOT = "reflex___state____state"


def val(snap: dict, key: str) -> str:
    return snap[key].split("=", 1)[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--api", required=True)
    ap.add_argument("--exp", type=float, default=5.0, help="token expiration configured on the server (s)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--shots", required=True)
    ap.add_argument("--label", default="run")
    ap.add_argument("--skip", nargs="*", default=[])
    ap.add_argument("--touch", default=None, help="app source file to touch to trigger a dev backend reload (scenario I2)")
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    shots = Path(args.shots); shots.mkdir(parents=True, exist_ok=True)
    api = args.api.rstrip("/")
    wait_expire = args.exp + 2.5

    def runs():
        return http_json(f"{api}/api/runs")["runs"]

    def keys(tok):
        return http_json(f"{api}/api/keys?token={tok}")

    def state_keys(tok):
        k = keys(tok)
        return {n: t for n, t in k["keys"].items() if not n.startswith("token_manager")}

    def log_tail():
        return http_json(f"{api}/api/runs")["log"]

    def is_true_deltas(deltas):
        return [d for d in deltas if isinstance(d["update"], dict)
                and (d["update"].get("delta") or {}).get(ROOT, {}).get("is_hydrated_rx_state_") is True]

    manager = keys("x")["manager"]
    rec("rehydrate.manager", "pass", f"state manager in use: {manager}; token expiration {args.exp}s")

    with sync_playwright() as p:
        browser = launch(p)
        ctx = browser.new_context(viewport={"width": 1100, "height": 900})
        page = ctx.new_page()
        cap = Capture(page, args.label)

        def pump(seconds: float):
            """Sleep while letting Playwright dispatch websocket/console events."""
            page.wait_for_timeout(seconds * 1000)

        def load(path, expect_page):
            http_json(f"{api}/api/reset")
            if page.url.startswith(args.url):
                # fresh token -> fresh state for every scenario
                page.evaluate("() => window.sessionStorage.clear()")
            page.goto(args.url + path, wait_until="load")
            wait_text(page, "#hydrated", lambda t: t == "hydrated=true", 20)
            wait_text(page, "#loaded_page", lambda t: t == f"loaded_page={expect_page}", 10)
            pump(0.5)
            return snapshot(page, IDS)

        def expire(tok, name):
            t0 = time.time()
            pump(wait_expire)
            sk = state_keys(tok)
            gone = not sk if manager != "StateManagerDisk" else True
            rec(f"{name}.state_expired", "pass" if gone else "fail",
                f"waited {time.time() - t0:.1f}s; remaining state keys for token: {sk}")
            return gone

        # ---------------------------------------------------------------- A: #7073 backend event, no route
        if "backend_event" in args.skip:
            rec("A.skipped", "skipped", "scenario A skipped by --skip backend_event (0.9.10.post2 in-memory: it triggers the runaway on_load loop)")
        else:
          snap0 = load("/", "index")
          tok = token_of(page)
          r0 = runs()
          rec("A.initial_load", "pass" if r0["index"] == 1 and val(snap0, "hydrated") == "true" else "fail",
              f"runs={r0} snap={snap0} token={tok[:8]}")
          expire(tok, "A")
          fi = len(cap.ws_frames)
          res = http_json(f"{api}/api/enqueue?token={tok}&event=ping")
          pump(1.5)
          s1 = snapshot(page, IDS); r1 = runs(); d = cap.deltas(fi); hd = hydrate_deltas(d)
          ok = (r1["index"] == 1 and r1["404"] == 0 and r1["ping"] == 1 and len(hd) == 1
                and len(is_true_deltas(d)) >= 1 and val(s1, "pings") == "1" and val(s1, "hydrated") == "true")
          rec("A.backend_event_on_expired_state", "pass" if ok else "fail",
              f"enqueue={res['results']} runs={r1} hydrate_deltas={len(hd)} is_hydrated_true_deltas={len(is_true_deltas(d))} "
              f"deltas={len(d)} snap={s1}", deltas=d)
          page.screenshot(path=str(shots / "A1_after_backend_event.png"))
          # A2: second backend event: must not rehydrate again
          fi = len(cap.ws_frames)
          res = http_json(f"{api}/api/enqueue?token={tok}&event=ping&n=2")
          pump(1.0)
          s2 = snapshot(page, IDS); r2 = runs(); d = cap.deltas(fi); hd = hydrate_deltas(d)
          ok = r2["ping"] == 3 and len(hd) == 0 and r2["index"] == 1 and r2["404"] == 0 and val(s2, "pings") == "3"
          rec("A.second_backend_event_no_rehydrate", "pass" if ok else "fail",
              f"enqueue={res['results']} runs={r2} hydrate_deltas={len(hd)} deltas={len(d)} snap={s2}", deltas=d)
          # A3: next frontend event carrying the route must still run the page's on_load
          fi = len(cap.ws_frames)
          page.click("#b-click")
          wait_text(page, "#loaded_page", lambda t: t == "loaded_page=index", 8)
          pump(1.0)
          s3 = snapshot(page, IDS); r3 = runs(); d = cap.deltas(fi); hd = hydrate_deltas(d)
          ok = (r3["index"] == 2 and r3["404"] == 0 and r3["click"] == 1 and len(hd) == 1
                and val(s3, "loaded_page") == "index" and val(s3, "clicks") == "1" and val(s3, "pings") == "3"
                and val(s3, "hydrated") == "true")
          rec("A.routed_event_after_routeless_rehydrate_runs_on_load", "pass" if ok else "fail",
              f"runs={r3} hydrate_deltas={len(hd)} deltas={len(d)} snap={s3}", deltas=d)
          page.screenshot(path=str(shots / "A3_after_click.png"))
          # A4: another click right away: no rehydrate
          fi = len(cap.ws_frames)
          page.click("#b-click")
          wait_text(page, "#clicks", lambda t: t == "clicks=2", 8)
          pump(0.5)
          r4 = runs(); d = cap.deltas(fi); hd = hydrate_deltas(d)
          rec("A.click_while_fresh_no_rehydrate", "pass" if len(hd) == 0 and r4["index"] == 2 else "fail",
              f"runs={r4} hydrate_deltas={len(hd)} deltas={len(d)}")

        # ---------------------------------------------------------------- B: #7072 post-eviction fallback via frontend event
        snap0 = load("/page-b", "page-b")
        tok = token_of(page)
        page.fill("#i-name", "alice"); page.locator("#i-name").blur()
        wait_text(page, "#name", lambda t: t == "name=alice", 8)
        page.fill("#i-flavor", "mint"); page.locator("#i-flavor").blur()
        wait_text(page, "#flavor", lambda t: t == "flavor=mint", 8)
        page.click("#b-click")
        wait_text(page, "#clicks", lambda t: t == "clicks=1", 8)
        page.click("#b-other")
        wait_text(page, "#other_count", lambda t: t == "other_count=1", 8)
        ls_before = page.evaluate("() => localStorage.getItem('rh_name')")
        ck_before = page.evaluate("() => document.cookie")
        sB = snapshot(page, IDS); rB = runs()
        rec("B.setup", "pass" if val(sB, "name") == "alice" and val(sB, "flavor") == "mint" and val(sB, "clicks") == "1" and val(sB, "other_count") == "1" and rB["page-b"] == 1 else "fail",
            f"snap={sB} runs={rB} localStorage.rh_name={ls_before!r} cookie={ck_before!r}")
        page.screenshot(path=str(shots / "B0_before_expiry.png"))
        expire(tok, "B")
        fi = len(cap.ws_frames)
        page.click("#b-click")
        wait_text(page, "#load_seq", lambda t: t != val(sB, "load_seq") and t != "load_seq=" , 8)
        pump(1.5)
        s = snapshot(page, IDS); r = runs(); d = cap.deltas(fi); hd = hydrate_deltas(d)
        ls_after = page.evaluate("() => localStorage.getItem('rh_name')")
        ck_after = page.evaluate("() => document.cookie")
        rehydrated = (len(hd) == 1 and r["page-b"] == 2 and r["404"] == 0 and val(s, "loaded_page") == "page-b"
                      and val(s, "hydrated") == "true" and len(is_true_deltas(d)) >= 1)
        rec("B.click_after_eviction_rehydrates_and_reruns_on_load", "pass" if rehydrated else "fail",
            f"runs={r} hydrate_deltas={len(hd)} is_hydrated_true={len(is_true_deltas(d))} deltas={len(d)} snap={s}", deltas=d)
        rec("B.clicks_counter_after_eviction", "anomaly" if val(s, "clicks") != "2" else "pass",
            f"clicks after eviction+click = {val(s, 'clicks')} (state was evicted so 1 is expected from a fresh state; 2 would mean state survived)")
        # client storage: is the UI showing the browser-held values after rehydrate?
        cs_ok = val(s, "name") == "alice" and val(s, "flavor") == "mint"
        rec("B.client_storage_resynced_after_rehydrate", "pass" if cs_ok else "anomaly",
            f"UI name={val(s, 'name')!r} flavor={val(s, 'flavor')!r}; browser localStorage.rh_name={ls_after!r} cookie={ck_after!r}")
        n_sub = [len(x["update"].get("delta") or {}) for x in hd]
        rec("B.other_substate_after_rehydrate", "pass" if val(s, "other_count") == "0" else "anomaly",
            f"UI other_count={val(s, 'other_count')!r} after eviction+rehydrate (backend OtherState is fresh => 0 expected; "
            f"'1' means the hydrate delta did not cover OtherState). substates in hydrate delta(s): {n_sub}")
        page.screenshot(path=str(shots / "B1_after_eviction_click.png"))
        # a later event on OtherState: what does the UI show then?
        fi = len(cap.ws_frames)
        page.click("#b-other")
        pump(1.5)
        s = snapshot(page, IDS); r = runs(); d = cap.deltas(fi); hd = hydrate_deltas(d)
        rec("B.bump_other_after_rehydrate", "pass" if val(s, "other_count") == "1" and len(hd) == 0 else "anomaly",
            f"UI other_count={val(s, 'other_count')!r} hydrate_deltas={len(hd)} deltas={len(d)} runs={r} snap={s}", deltas=d)
        # does a full reload bring client storage back?
        page.reload(wait_until="load")
        wait_text(page, "#hydrated", lambda t: t == "hydrated=true", 20)
        wait_text(page, "#name", lambda t: t == "name=alice", 8)
        s = snapshot(page, IDS)
        rec("B.client_storage_after_full_reload", "pass" if val(s, "name") == "alice" and val(s, "flavor") == "mint" else "fail", f"snap={s}")

        # ---------------------------------------------------------------- C: dynamic route arg after eviction
        snap0 = load("/item/abc", "item")
        tok = token_of(page)
        item0 = val(snapshot(page, IDS), "item_arg")
        rec("C.initial_item_arg", "pass" if item0 == "abc" else "fail", f"item_arg after initial load={item0!r}")
        expire(tok, "C")
        fi = len(cap.ws_frames)
        page.click("#b-click")
        wait_text(page, "#load_seq", lambda t: t == "load_seq=1", 8)
        pump(1.0)
        s = snapshot(page, IDS); r = runs(); d = cap.deltas(fi); hd = hydrate_deltas(d); item1 = val(s, "item_arg")
        ok = len(hd) == 1 and r["item"] == 2 and r["404"] == 0 and val(s, "loaded_page") == "item" and item1 == "abc"
        rec("C.dynamic_route_rehydrate_keeps_arg", "pass" if ok else "fail",
            f"runs={r} hydrate_deltas={len(hd)} item_arg before={item0} after={item1} snap={s} log={log_tail()[-4:]}", deltas=d)

        # ---------------------------------------------------------------- D: 404 page eviction (custom 404 loader must run once, not fan out)
        http_json(f"{api}/api/reset")
        page.goto(args.url + "/nope", wait_until="load")
        wait_text(page, "#hydrated", lambda t: t == "hydrated=true", 20)
        wait_text(page, "#loaded_page", lambda t: t == "loaded_page=404", 10)
        tok = token_of(page)
        r0 = runs()
        expire(tok, "D")
        fi = len(cap.ws_frames)
        page.click("#b-click")
        wait_text(page, "#load_seq", lambda t: t == "load_seq=1", 8)
        pump(1.5)
        s = snapshot(page, IDS); r = runs(); d = cap.deltas(fi); hd = hydrate_deltas(d)
        rec("D.custom_404_rehydrate_once", "pass" if r["404"] == 2 and len(hd) == 1 and r0["404"] == 1 else "fail",
            f"runs before={r0} after={r} hydrate_deltas={len(hd)} snap={s}", deltas=d)
        page.screenshot(path=str(shots / "D_404_after_click.png"))

        # ---------------------------------------------------------------- E: navigation during rehydrate
        snap0 = load("/", "index")
        tok = token_of(page)
        expire(tok, "E")
        fi = len(cap.ws_frames)
        page.click("#b-click")
        page.click("#l-b")
        wait_text(page, "#title", lambda t: t == "page-b", 8)
        wait_text(page, "#hydrated", lambda t: t == "hydrated=true", 8)
        pump(2.0)
        s = snapshot(page, IDS); r = runs(); d = cap.deltas(fi); hd = hydrate_deltas(d)
        ok = val(s, "loaded_page") == "page-b" and val(s, "hydrated") == "true" and r["404"] == 0 and r["page-b"] >= 1 and val(s, "path") == "/page-b"
        rec("E.navigate_during_rehydrate", "pass" if ok else "fail",
            f"runs={r} hydrate_deltas={len(hd)} deltas={len(d)} snap={s} log={log_tail()[-6:]}", deltas=d)
        page.screenshot(path=str(shots / "E_nav_during_rehydrate.png"))

        # ---------------------------------------------------------------- F: background task running across expiry
        snap0 = load("/", "index")
        tok = token_of(page)
        fi = len(cap.ws_frames)
        page.click("#b-slowbg")
        wait_text(page, "#bg_status", lambda t: t == "bg_status=started", 8)
        pump(wait_expire)
        sk = state_keys(tok)
        rec("F.state_expired_while_bg_running", "pass" if not sk or manager == "StateManagerDisk" else "anomaly", f"state keys during bg sleep: {sk}")
        bgs = wait_text(page, "#bg_status", lambda t: t.startswith("bg_status=finished"), 8)
        pump(1.0)
        s = snapshot(page, IDS); r = runs(); d = cap.deltas(fi); hd = hydrate_deltas(d)
        rec("F.bg_task_finishes_after_expiry", "pass" if bgs.startswith("bg_status=finished") and val(s, "clicks") == "100" else "fail",
            f"bg_status={bgs} runs={r} hydrate_deltas={len(hd)} deltas={len(d)} snap={s}", deltas=d)
        # the following frontend event should rehydrate (router_data was lost) and run on_load once
        fi = len(cap.ws_frames)
        page.click("#b-click")
        wait_text(page, "#clicks", lambda t: t == "clicks=101", 8)
        pump(1.5)
        s = snapshot(page, IDS); r = runs(); d = cap.deltas(fi); hd = hydrate_deltas(d)
        rec("F.click_after_bg_wrote_fresh_state", "pass" if r["404"] == 0 and val(s, "clicks") == "101" and val(s, "hydrated") == "true" else "fail",
            f"runs={r} hydrate_deltas={len(hd)} deltas={len(d)} snap={s} log={log_tail()[-5:]}", deltas=d)
        page.screenshot(path=str(shots / "F_bg_across_expiry.png"))

        # ---------------------------------------------------------------- G: second tab opened from the first (sessionStorage copied)
        snap0 = load("/", "index")
        tok1 = token_of(page)
        with ctx.expect_page() as pinfo:
            page.evaluate("() => window.open('/page-b', '_blank')")
        page2 = pinfo.value
        cap2 = Capture(page2, args.label + "_tab2")
        page2.wait_for_load_state("load")
        wait_text(page2, "#hydrated", lambda t: t == "hydrated=true", 20)
        wait_text(page2, "#loaded_page", lambda t: t == "loaded_page=page-b", 10)
        pump(0.5)
        tok2 = token_of(page2)
        r = runs()
        rec("G.second_tab_token", "pass" if tok2 != tok1 else "anomaly",
            f"tab1 token={tok1[:8]} tab2 token={tok2[:8]} (same={tok1 == tok2}) runs={r}")
        pump(wait_expire)
        fi1 = len(cap.ws_frames); fi2 = len(cap2.ws_frames)
        page.click("#b-click")
        wait_text(page, "#load_seq", lambda t: t == "load_seq=1", 8)
        pump(1.0); page2.wait_for_timeout(500)
        s1 = snapshot(page, IDS); s2 = snapshot(page2, IDS); r = runs(); d1 = cap.deltas(fi1); d2 = cap2.deltas(fi2)
        ok = len(hydrate_deltas(d1)) == 1 and len(d2) == 0 and val(s1, "loaded_page") == "index" and val(s2, "loaded_page") == "page-b"
        rec("G.tab1_rehydrate_isolated_from_tab2", "pass" if ok else "fail",
            f"tab1 deltas={len(d1)} hydrate={len(hydrate_deltas(d1))} tab2 deltas={len(d2)} runs={r} s1={s1} s2={s2}")
        fi2 = len(cap2.ws_frames)
        page2.click("#b-click")
        wait_text(page2, "#load_seq", lambda t: t == "load_seq=1", 8)
        page2.wait_for_timeout(1000)
        s2 = snapshot(page2, IDS); r = runs(); d2 = cap2.deltas(fi2)
        rec("G.tab2_rehydrates_own_page", "pass" if len(hydrate_deltas(d2)) == 1 and val(s2, "loaded_page") == "page-b" and r["404"] == 0 else "fail",
            f"tab2 deltas={len(d2)} hydrate={len(hydrate_deltas(d2))} runs={r} s2={s2}")
        an2 = cap2.anomalies()
        rec("G.tab2_browser_anomalies", "pass" if not any(an2[k] for k in an2 if k != "label") else "anomaly", str(an2))
        page2.close()

        # ---------------------------------------------------------------- H: backend event for a token nobody is connected with
        if "unknown_token" not in args.skip:
            http_json(f"{api}/api/reset")
            rnd = str(uuid.uuid4())
            t0 = time.time()
            try:
                res = http_json(f"{api}/api/enqueue?token={rnd}&event=ping", timeout=20)
            except Exception as ex:  # noqa: BLE001
                res = {"results": [f"http error {type(ex).__name__}: {ex}"]}
            pump(2.0)
            r = runs()
            rec("H.backend_event_unknown_token", "pass" if r["404"] == 0 and r["index"] == 0 and r["ping"] == 1 else "fail",
                f"took {time.time() - t0:.1f}s enqueue={res['results']} runs={r} log={log_tail()[-6:]}")
            pump(2.0)
            r2 = runs()
            rec("H.no_runaway_after_2s", "pass" if r2 == r else "fail", f"runs 2s later={r2}")

        # ---------------------------------------------------------------- I: websocket dropped by the server after the state expired
        if "reconnect" not in args.skip:
            snap0 = load("/page-b", "page-b")
            tok = token_of(page)
            page.fill("#i-name", "bob"); page.locator("#i-name").blur()
            wait_text(page, "#name", lambda t: t == "name=bob", 8)
            page.click("#b-click"); wait_text(page, "#clicks", lambda t: t == "clicks=1", 8)
            pump(wait_expire)
            sk = state_keys(tok)
            fi = len(cap.ws_frames)
            kicked = http_json(f"{api}/api/kick?token={tok}&mode=eio")
            # wait for the client to reconnect and re-hydrate
            wait_text(page, "#load_seq", lambda t: t == "load_seq=1", 15)
            pump(3.0)
            s = snapshot(page, IDS); r = runs(); d = cap.deltas(fi); hd = hydrate_deltas(d)
            sent = cap.sent_events(fi)
            sent_names = [e["event"].get("name", "?").rsplit(".", 1)[-1] for e in sent if isinstance(e["event"], dict)]
            tok_after = token_of(page)
            ok = (val(s, "hydrated") == "true" and r["page-b"] == 2 and r["404"] == 0 and val(s, "loaded_page") == "page-b"
                  and len(hd) == 1 and val(s, "name") == "bob" and tok_after == tok)
            rec("I.server_dropped_socket_after_expiry_reconnects", "pass" if ok else "fail",
                f"kicked={kicked} state keys before kick={sk} token same={tok == tok_after} runs={r} hydrate_deltas={len(hd)} "
                f"deltas={len(d)} client sent={sent_names} snap={s} log={log_tail()[-6:]}", deltas=d)
            page.screenshot(path=str(shots / "I_reconnect.png"))
            fi = len(cap.ws_frames)
            page.click("#b-click"); pump(1.5)
            s = snapshot(page, IDS); r = runs(); d = cap.deltas(fi); hd = hydrate_deltas(d)
            rec("I.click_after_reconnect_no_extra_rehydrate", "pass" if val(s, "clicks") == "1" and r["404"] == 0 and len(hd) == 0 and r["page-b"] == 2 else "anomaly",
                f"runs={r} hydrate_deltas={len(hd)} deltas={len(d)} snap={s}")
            ws_events = [f for f in cap.ws_frames[fi:] if f["dir"] in ("open", "close")]
            rec("I.ws_lifecycle_after_kick", "anomaly" if not ws_events else "pass",
                f"websocket open/close events seen after the engine.io close packet: {ws_events}")

        # ---------------------------------------------------------------- I2: dev backend reload (touch app file) while the client is connected
        if args.touch and "reload" not in args.skip:
            snap0 = load("/page-b", "page-b")
            tok = token_of(page)
            page.fill("#i-name", "carol"); page.locator("#i-name").blur()
            wait_text(page, "#name", lambda t: t == "name=carol", 8)
            page.click("#b-click"); wait_text(page, "#clicks", lambda t: t == "clicks=1", 8)
            r0 = runs()
            fi = len(cap.ws_frames)
            Path(args.touch).touch()
            # wait for the backend to come back and the client to reconnect + rehydrate
            t_end = time.time() + 40
            while time.time() < t_end:
                pump(1.0)
                try:
                    r = runs()
                except Exception:  # noqa: BLE001
                    continue
                if r["page-b"] >= 1 and r0["page-b"] > 0 and r["page-b"] != r0["page-b"]:
                    break
                if r["page-b"] == 1 and r0["page-b"] == 1 and any(f["dir"] == "open" for f in cap.ws_frames[fi:]):
                    # counters were reset by the reload; a new socket opened
                    break
            pump(3.0)
            s = snapshot(page, IDS); r = runs(); d = cap.deltas(fi); hd = hydrate_deltas(d)
            sent = cap.sent_events(fi)
            sent_names = [e["event"].get("name", "?").rsplit(".", 1)[-1] for e in sent if isinstance(e["event"], dict)]
            ws_events = [f["dir"] for f in cap.ws_frames[fi:] if f["dir"] in ("open", "close")]
            tok_after = token_of(page)
            ok = val(s, "hydrated") == "true" and val(s, "loaded_page") == "page-b" and r["404"] == 0 and tok_after == tok
            rec("I2.dev_backend_reload_reconnect", "pass" if ok else "fail",
                f"runs (counters reset by reload)={r} hydrate_deltas={len(hd)} deltas={len(d)} ws={ws_events} client sent={sent_names} "
                f"snap={s} (clicks: {val(s, 'clicks')} -> state {'survived' if val(s, 'clicks') == '1' else 'was lost'}; name: {val(s, 'name')!r})",
                deltas=d)
            page.screenshot(path=str(shots / "I2_dev_reload.png"))
            fi = len(cap.ws_frames)
            page.click("#b-click"); pump(1.5)
            s = snapshot(page, IDS); r = runs(); d = cap.deltas(fi); hd = hydrate_deltas(d)
            rec("I2.click_after_reload", "pass" if val(s, "hydrated") == "true" and r["404"] == 0 and val(s, "clicks") in ("1", "2") else "fail",
                f"runs={r} hydrate_deltas={len(hd)} deltas={len(d)} snap={s}")

        an = cap.anomalies()
        rec("rehydrate.browser_anomalies", "pass" if not any(an[k] for k in an if k != "label") else "anomaly", str(an))
        dump(out / "results.json", RESULTS)
        dump(out / "ws_frames.json", cap.ws_frames)
        dump(out / "console.json", cap.console)
        dump(out / "server_log_tail.json", http_json(f"{api}/api/runs"))
        ctx.close(); browser.close()
    return 0 if all(r["status"] == "pass" for r in RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
