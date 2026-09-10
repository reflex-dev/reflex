"""Drive bgflush_app in Chromium and check #6995 behaviour (bg handler raise -> delta still flushed).

Usage: NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python pw_bgflush.py \
    --url http://localhost:3220 --api http://localhost:8220 --out logs/pw_bgflush_smoke --shots shots/smoke --label smoke
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from playwright.sync_api import sync_playwright  # noqa: E402
from pwlib import RESULTS, Capture, dump, hydrate_deltas, http_json, launch, rec, snapshot, text_of, wait_text  # noqa: E402

IDS = ["beat", "count", "note", "where"]


def num(t: str) -> int:
    return int(t.split("=", 1)[1])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--api", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--shots", required=True)
    ap.add_argument("--label", default="run")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    shots = Path(args.shots)
    shots.mkdir(parents=True, exist_ok=True)
    api = args.api.rstrip("/")

    http_json(f"{api}/api/reset")
    with sync_playwright() as p:
        browser = launch(p)
        ctx = browser.new_context(viewport={"width": 1100, "height": 800})
        page = ctx.new_page()
        cap = Capture(page, args.label)
        page.goto(args.url + "/", wait_until="load")
        wait_text(page, "#beat", lambda t: t != "beat=0" and t != "<missing>", 20)
        time.sleep(0.5)
        page.screenshot(path=str(shots / "01_index.png"))
        base = snapshot(page, IDS)
        rec("bgflush.load", "pass" if base["beat"].startswith("beat=") and num(base["beat"]) > 0 else "fail",
            f"initial snapshot {base}")

        def api_state():
            return http_json(f"{api}/api/state")

        def run_step(name, button, expect, settle=3.0, **kw):
            """Click a button, wait `settle`, compare before/after; expect is a callable (before, after, deltas, exc) -> (ok, msg)."""
            before = snapshot(page, IDS)
            exc_before = list(api_state()["exc"])
            frame_idx = len(cap.ws_frames)
            page.click(f"#{button}")
            t_end = time.time() + settle
            # wait until the exception handler ran (exc grows) or settle expires, then wait a little more for deltas
            while time.time() < t_end:
                if len(api_state()["exc"]) > len(exc_before):
                    break
                time.sleep(0.1)
            time.sleep(1.0)
            after = snapshot(page, IDS)
            deltas = cap.deltas(frame_idx)
            exc_new = api_state()["exc"][len(exc_before):]
            with_beat = [d for d in deltas if isinstance(d["update"], dict) and any(
                "beat_rx_state_" in (v or {}) for v in (d["update"].get("delta") or {}).values())]
            events_only = [d for d in deltas if isinstance(d["update"], dict) and not d["update"].get("delta") and d["update"].get("events")]
            ok, msg = expect(before, after, deltas, exc_new)
            rec(name, "pass" if ok else "fail",
                f"{msg} | before={before} after={after} | deltas={len(deltas)} with_beat={len(with_beat)} events_only={len(events_only)} | new_exc={exc_new}",
                deltas=deltas, exc_new=exc_new)
            page.screenshot(path=str(shots / f"{name}.png"))
            return before, after, deltas, exc_new

        # 1. control: foreground noop flushes a delta with the uncached var
        run_step("bgflush.fg_noop_control", "b-fg",
                 lambda b, a, d, e: (num(a["beat"]) > num(b["beat"]) and not e, "fg event refreshed beat"))
        # 2. control: bg handler, no ctx, no raise -> compat flush
        run_step("bgflush.bg_ok_noctx_control", "b-ok",
                 lambda b, a, d, e: (num(a["beat"]) > num(b["beat"]) and not e, "bg no-ctx normal return refreshed beat"))
        # 3. THE FIX: bg handler, no ctx, raises -> compat flush must still run and exc reaches handler
        run_step("bgflush.noctx_raise_flushes_delta", "b-noctx",
                 lambda b, a, d, e: (num(a["beat"]) > num(b["beat"]) and e == ["RuntimeError: boom-noctx"],
                                     "expect beat refreshed AND handler got RuntimeError: boom-noctx"))
        toast = page.locator("text=handled: RuntimeError: boom-noctx")
        rec("bgflush.noctx_raise_toast_visible", "pass" if toast.count() > 0 else "fail",
            f"exception-handler toast count={toast.count()}")
        # 4. raises after ctx exit: ctx exit already flushed (count+1), fallback skipped, exc reaches handler
        run_step("bgflush.after_ctx_raise", "b-after",
                 lambda b, a, d, e: (num(a["count"]) == num(b["count"]) + 1 and "after-ctx" in a["note"]
                                     and e == ["RuntimeError: boom-after-ctx"], "count+1, note updated, exc handled"))
        # 5. raises inside ctx
        run_step("bgflush.inside_ctx_raise", "b-inside",
                 lambda b, a, d, e: (e == ["RuntimeError: boom-inside-ctx"],
                                     f"exc handled; count changed by {num(a['count']) - num(b['count'])} (mutation before raise inside ctx)"))
        # 6. yields a frontend event then raises (no ctx)
        run_step("bgflush.yield_then_raise", "b-yield",
                 lambda b, a, d, e: (num(a["beat"]) > num(b["beat"]) and e == ["RuntimeError: boom-after-yield"],
                                     "beat refreshed + exc handled"))
        rec("bgflush.yield_then_raise_toast", "pass" if page.locator("text=yielded-before-raise").count() > 0 else "fail",
            f"yielded toast count={page.locator('text=yielded-before-raise').count()}")
        # 7. yields a state event then raises (no ctx)
        run_step("bgflush.yield_state_event_then_raise", "b-yieldstate",
                 lambda b, a, d, e: (a["note"] == "note=bump_note ran" and num(a["beat"]) > num(b["beat"])
                                     and e == ["RuntimeError: boom-after-yield-state-event"],
                                     "yielded state event ran, beat refreshed, exc handled"))
        # 8. flush itself fails: handler exception must still be the one delivered; flush error logged
        run_step("bgflush.flush_failure_does_not_mask", "b-flushfail",
                 lambda b, a, d, e: (e == ["RuntimeError: boom-flush-fails"],
                                     "handler's RuntimeError delivered (not the ValueError from the failing flush)"))
        run_step("bgflush.clear_flush_fail", "b-clearff",
                 lambda b, a, d, e: (a["note"] == "note=flush_fail cleared" and not e, "cleared"))
        # 9. navigate client-side to /other and raise again there (router-derived text)
        page.click("#l-otherq")
        w = wait_text(page, "#where", lambda t: "path=/other" in t, 10)
        rec("bgflush.navigate_other", "pass" if "path=/other" in w and "x=1" in w else "fail", f"where after nav: {w}")
        run_step("bgflush.noctx_raise_on_other", "b-noctx",
                 lambda b, a, d, e: (num(a["beat"]) > num(b["beat"]) and e == ["RuntimeError: boom-noctx"]
                                     and "path=/other" in a["where"], "beat refreshed on /other, where intact"))
        # 10. page whose on_load is the raising bg handler
        exc_before = len(api_state()["exc"])
        frame_idx = len(cap.ws_frames)
        page.click("#l-onload")
        wait_text(page, "#where", lambda t: "path=/onload-bg" in t, 10)
        t_end = time.time() + 6
        while time.time() < t_end and len(api_state()["exc"]) <= exc_before:
            time.sleep(0.1)
        time.sleep(1.0)
        hyd = page.evaluate("() => document.body.innerText")
        exc_new = api_state()["exc"][exc_before:]
        deltas = cap.deltas(frame_idx)
        hyd_true = [d for d in deltas if isinstance(d["update"], dict) and (d["update"].get("delta") or {}).get(
            "reflex___state____state", {}).get("is_hydrated_rx_state_") is True]
        snap = snapshot(page, IDS)
        rec("bgflush.onload_bg_raise", "pass" if exc_new == ["RuntimeError: boom-noctx"] and hyd_true else "fail",
            f"on_load bg raise: exc={exc_new} is_hydrated_true_deltas={len(hyd_true)} deltas={len(deltas)} snap={snap}",
            deltas=deltas)
        page.screenshot(path=str(shots / "10_onload_bg.png"))
        # 11. full reload of /onload-bg (initial events path: hydrate + on_load chain)
        exc_before = len(api_state()["exc"])
        frame_idx = len(cap.ws_frames)
        page.reload(wait_until="load")
        wait_text(page, "#beat", lambda t: t != "<missing>", 20)
        t_end = time.time() + 6
        while time.time() < t_end and len(api_state()["exc"]) <= exc_before:
            time.sleep(0.1)
        time.sleep(1.0)
        exc_new = api_state()["exc"][exc_before:]
        deltas = cap.deltas(frame_idx)
        hyd_true = [d for d in deltas if isinstance(d["update"], dict) and (d["update"].get("delta") or {}).get(
            "reflex___state____state", {}).get("is_hydrated_rx_state_") is True]
        rec("bgflush.onload_bg_raise_fullreload", "pass" if exc_new == ["RuntimeError: boom-noctx"] and hyd_true else "fail",
            f"full reload: exc={exc_new} is_hydrated_true_deltas={len(hyd_true)} deltas={len(deltas)} snap={snapshot(page, IDS)}",
            deltas=deltas)
        page.screenshot(path=str(shots / "11_onload_bg_reload.png"))

        an = cap.anomalies()
        rec("bgflush.browser_anomalies", "pass" if not any(an[k] for k in an if k != "label") else "anomaly", str(an))
        dump(out / "results.json", RESULTS)
        dump(out / "ws_frames.json", cap.ws_frames)
        dump(out / "console.json", cap.console)
        dump(out / "api_state_final.json", api_state())
        ctx.close()
        browser.close()
    return 0 if all(r["status"] == "pass" for r in RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
