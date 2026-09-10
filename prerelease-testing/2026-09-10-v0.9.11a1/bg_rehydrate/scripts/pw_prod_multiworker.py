"""UI-only check of #7073/#7072 against a MULTI-WORKER prod server (module-level counters are per worker,
so only the browser is trusted here). Usage: pw_prod_multiworker.py --url http://localhost:3223 --exp 5 --out logs/pw_prod_mw"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from playwright.sync_api import sync_playwright  # noqa: E402
from pwlib import RESULTS, Capture, dump, http_json, hydrate_deltas, launch, rec, snapshot, token_of, wait_text  # noqa: E402

IDS = ["title", "hydrated", "path", "loaded_page", "load_seq", "clicks", "pings", "name", "other_count"]


def val(s, k):
    return s[k].split("=", 1)[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--exp", type=float, default=5.0)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_context().new_page()
        cap = Capture(page, "prod_mw")
        page.goto(args.url + "/", wait_until="load")
        wait_text(page, "#hydrated", lambda t: t == "hydrated=true", 30)
        wait_text(page, "#loaded_page", lambda t: t == "loaded_page=index", 10)
        tok = token_of(page)
        s0 = snapshot(page, IDS)
        page.wait_for_timeout((args.exp + 2.5) * 1000)
        keys = http_json(f"{args.url}/api/keys?token={tok}")
        fi = len(cap.ws_frames)
        res = [http_json(f"{args.url}/api/enqueue?token={tok}&event=ping&wait=0")["results"] for _ in range(3)]
        page.wait_for_timeout(2500)
        s1 = snapshot(page, IDS); d = cap.deltas(fi); hd = hydrate_deltas(d)
        ok = val(s1, "pings") == "3" and len(hd) == 1 and val(s1, "hydrated") == "true" and val(s1, "load_seq") == "0"
        rec("MW.three_backend_events_after_expiry", "pass" if ok else "fail",
            f"keys before={keys} enqueue={res} hydrate_deltas={len(hd)} deltas={len(d)} before={s0} after={s1}", deltas=d)
        fi = len(cap.ws_frames)
        page.click("#b-click")
        wait_text(page, "#loaded_page", lambda t: t == "loaded_page=index", 10)
        page.wait_for_timeout(1500)
        s2 = snapshot(page, IDS); d = cap.deltas(fi); hd = hydrate_deltas(d)
        ok = len(hd) == 1 and val(s2, "clicks") == "1" and val(s2, "load_seq") == "1" and val(s2, "hydrated") == "true"
        rec("MW.routed_click_reruns_on_load", "pass" if ok else "fail", f"hydrate_deltas={len(hd)} deltas={len(d)} snap={s2}", deltas=d)
        # eviction + click (B) on /page-b
        page.evaluate("() => window.sessionStorage.clear()")
        page.goto(args.url + "/page-b", wait_until="load")
        wait_text(page, "#loaded_page", lambda t: t == "loaded_page=page-b", 15)
        page.fill("#i-name", "alice"); page.locator("#i-name").blur(); wait_text(page, "#name", lambda t: t == "name=alice", 8)
        page.click("#b-click"); wait_text(page, "#clicks", lambda t: t == "clicks=1", 8)
        page.wait_for_timeout((args.exp + 2.5) * 1000)
        fi = len(cap.ws_frames)
        page.click("#b-click")
        wait_text(page, "#load_seq", lambda t: t == "load_seq=1", 10)
        page.wait_for_timeout(1500)
        s3 = snapshot(page, IDS); d = cap.deltas(fi); hd = hydrate_deltas(d)
        ok = len(hd) == 1 and val(s3, "clicks") == "1" and val(s3, "loaded_page") == "page-b" and val(s3, "hydrated") == "true"
        rec("MW.click_after_eviction_rehydrates", "pass" if ok else "fail", f"hydrate_deltas={len(hd)} deltas={len(d)} snap={s3}", deltas=d)
        an = cap.anomalies()
        rec("MW.browser_anomalies", "pass" if not any(an[k] for k in an if k != "label") else "anomaly", str(an))
        dump(out / "results.json", RESULTS); dump(out / "ws_frames.json", cap.ws_frames)
        browser.close()
    return 0 if all(r["status"] == "pass" for r in RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
