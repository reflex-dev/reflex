"""Drive schema_app: state-schema hash on connect (#7553) and unknown substates (#7435).

    NO_PROXY=... $SB/envs/driver/bin/python drive_schema.py --url http://localhost:3227/ --out x.json \
        [--reloads 3] [--restart-cmd "<shell command that restarts the backend>"] [--hold 20]

Records per document load: navigation type, state-mismatch console warnings, unknown-substate
warnings, the new-version banner, and whether typed input survived.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
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
MISMATCH = "built for another version"
UNKNOWN = "unknown substate"
BANNER = "#reflex-new-version-banner"
HYDRATED = "() => document.querySelector('#hydrated')?.textContent === 'true'"
LOADS_JS = "() => parseInt(sessionStorage.getItem('__loads') || '0')"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--reloads", type=int, default=2)
    ap.add_argument("--restart-cmd", default=None)
    ap.add_argument("--hold", type=int, default=25, help="seconds to observe after the restart")
    ap.add_argument("--timeout", type=int, default=30000)
    args = ap.parse_args()
    base = args.url.rstrip("/")
    console, errors = [], []
    checks: list[dict] = []

    def chk(name, got, want):
        ok = got == want
        checks.append({"name": name, "ok": ok, "got": got, "want": want})
        print(f"[{'ok ' if ok else 'FAIL'}] {name}: got={got!r} want={want!r}")

    def n_mismatch():
        return sum(1 for c in console if MISMATCH in c["text"])

    def n_unknown():
        return sum(1 for c in console if UNKNOWN in c["text"])

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        ctx = browser.new_context()
        ctx.add_init_script("sessionStorage.setItem('__loads', String(parseInt(sessionStorage.getItem('__loads') || '0') + 1))")
        page = ctx.new_page()
        page.on("console", lambda m: console.append({"type": m.type, "text": m.text, "t": time.time()}))
        page.on("pageerror", lambda e: errors.append(str(e)))
        T = args.timeout
        page.goto(f"{base}/", wait_until="load", timeout=T)
        page.wait_for_function(HYDRATED, timeout=T)
        page.wait_for_timeout(500)
        chk("first load: no mismatch warning", n_mismatch(), 0)
        chk("first load: no banner", page.locator(BANNER).count(), 0)
        chk("first load: navigation type", page.evaluate("performance.getEntriesByType('navigation')[0].type"), "navigate")
        page.click("#inc")
        page.wait_for_function("() => document.querySelector('#count')?.textContent === '1'", timeout=T)
        page.click("#t1 .tally-inc")
        page.wait_for_function("() => document.querySelector('#t1 .tally-n')?.textContent === '1'", timeout=T)
        page.fill("#note-input", "typed-note")
        page.wait_for_function("() => document.querySelector('#note')?.textContent === 'typed-note'", timeout=T)
        for i in range(args.reloads):
            page.reload(wait_until="load", timeout=T)
            page.wait_for_function(HYDRATED, timeout=T)
            page.wait_for_timeout(400)
        chk(f"after {args.reloads} reloads: no mismatch warning", n_mismatch(), 0)
        chk("after reloads: no banner", page.locator(BANNER).count(), 0)
        chk("after reloads: count kept", page.text_content("#count"), "1")
        chk("after reloads: tally kept", page.text_content("#t1 .tally-n"), "1")
        for route in ("/second", "/item/5"):
            page.goto(f"{base}{route}", wait_until="load", timeout=T)
            page.wait_for_function(HYDRATED, timeout=T)
            page.wait_for_timeout(400)
        chk("prerendered routes: no mismatch warning", n_mismatch(), 0)
        chk("prerendered /item/5 iid", page.text_content("#iid"), "5")
        chk("second: tally t3 renders", page.text_content("#t3 .tally-n"), "0")
        page.goto(f"{base}/", wait_until="load", timeout=T)
        page.wait_for_function(HYDRATED, timeout=T)
        chk("no page errors so far", errors, [])
        loads_before = page.evaluate(LOADS_JS)
        page.fill("#free-input", "typed-free")
        mismatch_before = n_mismatch()
        if args.restart_cmd:
            t0 = time.time()
            print("[info] restarting backend:", args.restart_cmd)
            subprocess.run(args.restart_cmd, shell=True, check=False)
            print(f"[info] restart command done after {time.time() - t0:.1f}s; observing {args.hold}s")
            deadline = time.time() + args.hold
            timeline = []
            last = None
            while time.time() < deadline:
                try:
                    state = {
                        "t": round(time.time() - t0, 1),
                        "loads": page.evaluate(LOADS_JS),
                        "nav": page.evaluate("performance.getEntriesByType('navigation')[0].type"),
                        "banner": page.locator(BANNER).count(),
                        "hydrated": page.evaluate("document.querySelector('#hydrated')?.textContent"),
                        "free_input": page.evaluate("document.querySelector('#free-input')?.value"),
                        "mismatch": n_mismatch(),
                        "unknown": n_unknown(),
                    }
                except Exception as e:  # noqa: BLE001
                    state = {"t": round(time.time() - t0, 1), "err": str(e)[:80]}
                key = json.dumps({k: v for k, v in state.items() if k != "t"})
                if key != last:
                    timeline.append(state)
                    print("  ", state)
                    last = key
                time.sleep(0.5)
            final = timeline[-1] if timeline else {}
            checks.append({"name": "timeline after restart", "ok": True, "got": timeline, "want": "info"})
            chk("reloads caused by restart (loads delta)", final.get("loads", 0) - loads_before, final.get("loads", 0) - loads_before)
            chk("last_reloaded cooldown key set", page.evaluate("!!sessionStorage.getItem('reflex_last_reloaded_on_error')"), final.get("nav") == "reload")
            if final.get("hydrated") == "true":
                page.click("#inc")
                page.wait_for_timeout(1500)
                chk("events still work after restart", page.text_content("#count").isdigit(), True)
            chk("new mismatch warnings after restart", n_mismatch() - mismatch_before, n_mismatch() - mismatch_before)
        page.wait_for_timeout(300)
        browser.close()

    noisy = [c for c in console if not any(b.search(c["text"]) for b in BENIGN)]
    report = {"checks": checks, "n_fail": sum(1 for c in checks if not c["ok"]), "console": noisy, "pageerrors": errors,
              "mismatch_warnings": n_mismatch(), "unknown_substate_warnings": n_unknown()}
    Path(args.out).write_text(json.dumps(report, indent=1, ensure_ascii=False))
    print(f"fails={report['n_fail']} mismatch_warnings={n_mismatch()} unknown_substate_warnings={n_unknown()} console(non-benign)={len(noisy)} pageerrors={len(errors)}")
    for c in noisy[:12]:
        print("  console:", c["type"], c["text"][:200])
    return 0 if report["n_fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
