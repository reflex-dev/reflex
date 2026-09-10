"""Cross-worker delivery probe: load a page (no expiry), enqueue pings from the backend N times, and see
how many deltas reach the browser. Usage: pw_prod_crossworker.py --url http://localhost:3223 --n 6 --out logs/x"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from playwright.sync_api import sync_playwright  # noqa: E402
from pwlib import RESULTS, Capture, dump, http_json, launch, rec, snapshot, token_of, wait_text  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_context().new_page()
        cap = Capture(page, "xw")
        page.goto(args.url + "/", wait_until="load")
        wait_text(page, "#hydrated", lambda t: t == "hydrated=true", 30)
        wait_text(page, "#loaded_page", lambda t: t == "loaded_page=index", 10)
        tok = token_of(page)
        results = []
        for i in range(args.n):
            fi = len(cap.ws_frames)
            r = http_json(f"{args.url}/api/enqueue?token={tok}&event=ping&wait=1")
            page.wait_for_timeout(1200)
            d = cap.deltas(fi)
            ui = snapshot(page, ["pings"])["pings"]
            results.append({"i": i, "api": r["results"], "worker_runs_ping": r["runs"]["ping"], "deltas_received": len(d), "ui": ui})
            print(results[-1], flush=True)
        delivered = sum(1 for x in results if x["deltas_received"] > 0)
        rec("XW.backend_event_delta_delivery", "pass" if delivered == args.n else "fail",
            f"{delivered}/{args.n} backend-initiated pings produced a delta in the browser; final UI {results[-1]['ui']}; per call: {results}")
        # a frontend click afterwards: what does the UI show for pings (the backend truth)?
        page.click("#b-click"); page.wait_for_timeout(1500)
        rec("XW.ui_after_click", "pass", f"snapshot={snapshot(page, ['pings', 'clicks', 'loaded_page', 'load_seq'])}")
        dump(out / "results.json", RESULTS); dump(out / "ws_frames.json", cap.ws_frames)
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
