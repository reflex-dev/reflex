"""#7073 runaway probe: load '/', let the state expire, enqueue ONE backend event (wait=0 so the API returns),
then sample /api/runs for --sample seconds. A healthy server shows index=1, 404=0 and ping=1 throughout;
the pre-fix server shows the index loader count climbing by hundreds per second (and the backend at 100% CPU).

Usage: pw_runaway_probe.py --url http://localhost:3226 --api http://localhost:8226 --exp 5 --sample 6 --out logs/x --shots shots/x
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from playwright.sync_api import sync_playwright  # noqa: E402
from pwlib import RESULTS, Capture, dump, http_json, hydrate_deltas, launch, rec, snapshot, token_of, wait_text  # noqa: E402

IDS = ["hydrated", "path", "loaded_page", "load_seq", "clicks", "pings"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True); ap.add_argument("--api", required=True)
    ap.add_argument("--exp", type=float, default=5.0); ap.add_argument("--sample", type=float, default=6.0)
    ap.add_argument("--out", required=True); ap.add_argument("--shots", required=True)
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    shots = Path(args.shots); shots.mkdir(parents=True, exist_ok=True)
    api = args.api.rstrip("/")
    http_json(f"{api}/api/reset")
    samples = []
    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_context().new_page()
        cap = Capture(page, "runaway")
        page.goto(args.url + "/", wait_until="load")
        wait_text(page, "#hydrated", lambda t: t == "hydrated=true", 30)
        wait_text(page, "#loaded_page", lambda t: t == "loaded_page=index", 10)
        tok = token_of(page)
        page.wait_for_timeout((args.exp + 2.5) * 1000)
        keys = http_json(f"{api}/api/keys?token={tok}")
        fi = len(cap.ws_frames)
        t0 = time.time()
        res = http_json(f"{api}/api/enqueue?token={tok}&event=ping&wait=0", timeout=20)
        while time.time() - t0 < args.sample:
            page.wait_for_timeout(500)
            try:
                r = http_json(f"{api}/api/runs", timeout=10)["runs"]
            except Exception as ex:  # noqa: BLE001
                r = {"error": f"{type(ex).__name__}: {ex}"}
            samples.append({"t": round(time.time() - t0, 1), "runs": r, "ws_frames_received": sum(1 for f in cap.ws_frames[fi:] if f["dir"] == "recv")})
            print(samples[-1], flush=True)
        page.screenshot(path=str(shots / "runaway_probe.png"))
        snap = snapshot(page, IDS)
        d = cap.deltas(fi); hd = hydrate_deltas(d)
        last = samples[-1]["runs"]
        healthy = isinstance(last.get("index"), int) and last["index"] == 1 and last.get("404") == 0 and last.get("ping") == 1
        rec("RUNAWAY.single_backend_event_after_expiry", "pass" if healthy else "fail",
            f"state keys before={keys['keys']} enqueue={res['results']} runs after {args.sample}s={last} hydrate_deltas={len(hd)} "
            f"deltas={len(d)} ws frames received={samples[-1]['ws_frames_received']} snap={snap}")
        dump(out / "results.json", RESULTS); dump(out / "samples.json", samples); dump(out / "ws_frames.json", cap.ws_frames[:2000])
        browser.close()
    return 0 if healthy else 1


if __name__ == "__main__":
    sys.exit(main())
