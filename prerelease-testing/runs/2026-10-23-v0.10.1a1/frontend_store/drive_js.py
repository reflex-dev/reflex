"""Drive /js of fs_app: compiled-JS fixes (#7565 unary base, #7518 Unicode string ops,
#7544 error events without an Error object, #7573 tailwind important, #7587 dict props).

    NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
      $SB/envs/driver/bin/python drive_js.py --url http://localhost:3220 --out js.json [--negsq 0]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
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
    ap.add_argument("--out", required=True)
    ap.add_argument("--negsq", default="1")
    ap.add_argument("--nonelen", default="1")
    ap.add_argument("--timeout", type=int, default=20000)
    args = ap.parse_args()
    base = args.url.rstrip("/")
    checks: list[dict] = []
    console, errors = [], []

    def chk(name, got, want):
        ok = got == want
        checks.append({"name": name, "ok": ok, "got": got, "want": want})
        print(f"[{'ok ' if ok else 'FAIL'}] {name}: got={got!r} want={want!r}")

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        page = browser.new_context().new_page()
        page.on("console", lambda m: console.append({"type": m.type, "text": m.text}))
        page.on("pageerror", lambda e: errors.append(str(e)))
        T = args.timeout
        page.goto(f"{base}/js", wait_until="load", timeout=T)
        page.wait_for_function("() => document.querySelector('#hydrated')?.textContent === 'true'", timeout=T)

        def compare(expected_sel):
            exp = json.loads(page.text_content(expected_sel))
            for key, want in exp.items():
                if key in ("neg_sq", "neg_cube", "lit_neg_base") and args.negsq != "1":
                    continue
                if key == "none_len" and args.nonelen != "1":
                    continue
                got = page.text_content(f"#js-{key}")
                chk(f"js {key}", got, str(want))

        compare("#js-expected")
        page.click("#set2")
        page.wait_for_function("() => document.querySelector('#js-len')?.textContent === '2'", timeout=T)
        compare("#js-expected-2")
        if args.nonelen == "1":
            page.click("#set-n")
            page.wait_for_function("() => document.querySelector('#js-none_len')?.textContent === '2'", timeout=T)
            chk("js none_len after set", page.text_content("#js-none_len"), "2")

        # dict / style props
        chk("style padding from var", page.evaluate("getComputedStyle(document.querySelector('#styled')).paddingLeft"), "4px")
        chk("data-dict attr", page.get_attribute("#styled", "data-dict"), '{"a":[1,2],"b":{"c":"d"}}')
        color = page.evaluate("getComputedStyle(document.querySelector('#styled')).color")
        checks.append({"name": "styled color (tailwind important?)", "ok": True, "got": color, "want": "info"})
        print(f"[info] #styled computed color = {color} (red = tailwind important wins over inline blue)")

        # error events without an Error object must not throw a secondary TypeError
        before = len(errors)
        page.click("#err-noobj")
        page.wait_for_timeout(800)
        page.click("#err-onerror-direct")
        page.wait_for_timeout(800)
        page.click("#err-obj")
        page.wait_for_timeout(1500)
        new_errors = errors[before:]
        secondary = [e for e in new_errors if "Cannot read properties of undefined" in e or "reading 'name'" in e]
        chk("no secondary TypeError from error event without Error", secondary, [])
        checks.append({"name": "page errors seen during error-event test", "ok": True, "got": new_errors, "want": "info"})
        page.wait_for_timeout(300)
        browser.close()

    noisy = [c for c in console if not any(b.search(c["text"]) for b in BENIGN)]
    report = {"checks": checks, "n_fail": sum(1 for c in checks if not c["ok"]), "console": noisy, "pageerrors": errors}
    Path(args.out).write_text(json.dumps(report, indent=1, ensure_ascii=False))
    print(f"fails={report['n_fail']} console(non-benign)={len(noisy)} pageerrors={len(errors)}")
    for c in noisy[:30]:
        print("  console:", c["type"], c["text"][:300])
    for e in errors[:10]:
        print("  pageerror:", e[:300])
    return 0 if report["n_fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
