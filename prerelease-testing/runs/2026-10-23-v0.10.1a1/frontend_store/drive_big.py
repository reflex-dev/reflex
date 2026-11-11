"""Drive the bigstate app: load time, blank-page / stack-overflow detection, targeted updates.

    NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
      $SB/envs/driver/bin/python drive_big.py --url http://localhost:3226/ --read 50 --out big.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

CHROMIUM = "/opt/pw-browsers/chromium"
BENIGN = [
    re.compile(r"Hey developer.*HydrateFallback|reactrouter\.com/start/framework/route-module"),
    re.compile(r"\[vite\] (connecting|connected)"),
    re.compile(r"Download the React DevTools"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--read", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeout", type=int, default=60000)
    ap.add_argument("--screenshot", default=None)
    args = ap.parse_args()
    console, errors = [], []
    res: dict = {"url": args.url, "read": args.read}
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        page = browser.new_context().new_page()
        page.on("console", lambda m: console.append({"type": m.type, "text": m.text}))
        page.on("pageerror", lambda e: errors.append(str(e)))
        T = args.timeout
        t0 = time.time()
        page.goto(args.url, wait_until="load", timeout=T)
        res["load_ms"] = int((time.time() - t0) * 1000)
        try:
            page.wait_for_function("() => document.querySelector('#hydrated')?.textContent === 'true'", timeout=T)
            res["hydrated_ms"] = int((time.time() - t0) * 1000)
        except Exception as e:  # noqa: BLE001
            res["hydrated_ms"] = None
            res["hydrate_error"] = str(e)[:200]
        res["n_vals"] = page.evaluate("document.querySelectorAll('#vals .v').length")
        res["first_vals"] = page.evaluate("Array.from(document.querySelectorAll('#vals .v')).slice(0,3).map(e=>e.textContent)")
        res["last_val"] = page.evaluate("(document.querySelectorAll('#vals .v')[%d] || {}).textContent" % (args.read - 1))
        if res.get("hydrated_ms"):
            # targeted update: three substates in one event
            t1 = time.time()
            page.click("#bump")
            page.wait_for_function("() => document.querySelector('#ticks')?.textContent === '1'", timeout=T)
            res["bump_ms"] = int((time.time() - t1) * 1000)
            vals = page.evaluate("Array.from(document.querySelectorAll('#vals .v')).map(e=>e.textContent)")
            want = [str(i) for i in range(args.read)]
            for i in (0, args.read // 2, args.read - 1):
                want[i] = str(i + 1)
            res["bump_correct"] = vals == want
            if not res["bump_correct"]:
                res["bump_diff"] = [(i, vals[i], want[i]) for i in range(len(want)) if vals[i] != want[i]][:5]
            t2 = time.time()
            page.click("#inc-last")
            page.wait_for_function("() => document.querySelectorAll('#vals .v')[%d]?.textContent === '%d'" % (args.read - 1, args.read + 1), timeout=T)
            res["inc_last_ms"] = int((time.time() - t2) * 1000)
            # a full reload re-hydrates everything
            t3 = time.time()
            page.reload(wait_until="load", timeout=T)
            page.wait_for_function("() => document.querySelector('#hydrated')?.textContent === 'true'", timeout=T)
            res["reload_hydrated_ms"] = int((time.time() - t3) * 1000)
            res["after_reload_last"] = page.evaluate("(document.querySelectorAll('#vals .v')[%d] || {}).textContent" % (args.read - 1))
        if args.screenshot:
            Path(args.screenshot).parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=args.screenshot)
        browser.close()
    noisy = [c for c in console if not any(b.search(c["text"]) for b in BENIGN)]
    res["console"] = noisy[:30]
    res["pageerrors"] = errors[:10]
    res["stack_overflow"] = any("Maximum call stack" in e for e in errors) or any("Maximum call stack" in c["text"] for c in console)
    Path(args.out).write_text(json.dumps(res, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k not in ("console",)}, indent=1)[:3000])
    print("console:", [c["text"][:160] for c in noisy[:8]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
