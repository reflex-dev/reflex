"""Playwright driver for the client_error cluster.

Usage: python drive.py <frontend_url> <out_dir> <scenario>
scenarios: break | bgbreak | normal | postbreak
Captures console messages + screenshots. Exits nonzero on driver error.
"""

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

CHROMIUM = "/opt/pw-browsers/chromium"


def main():
    url = sys.argv[1]
    out = Path(sys.argv[2])
    scenario = sys.argv[3] if len(sys.argv) > 3 else "break"
    out.mkdir(parents=True, exist_ok=True)

    console_msgs = []
    page_errors = []
    failed_reqs = []

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM, headless=True)
        page = browser.new_page()
        page.on("console", lambda m: console_msgs.append(f"[{m.type}] {m.text}"))
        page.on("pageerror", lambda e: page_errors.append(str(e)))
        page.on(
            "requestfailed",
            lambda r: failed_reqs.append(f"{r.method} {r.url} :: {r.failure}"),
        )
        page.on(
            "response",
            lambda r: failed_reqs.append(f"HTTP {r.status} {r.url}")
            if r.status >= 400
            else None,
        )

        page.goto(url, wait_until="networkidle")
        # Wait for token (hydration complete)
        page.wait_for_function(
            "() => { const t = document.querySelector('#token'); return t && t.value && t.value.length > 0; }",
            timeout=30000,
        )
        token = page.eval_on_selector("#token", "el => el.value")
        print(f"TOKEN={token}")
        page.screenshot(path=str(out / f"{scenario}_01_loaded.png"))

        # Confirm socket works: bump once
        page.click("#bump-btn")
        page.wait_for_function(
            "() => document.querySelector('#counter').textContent === '1'",
            timeout=10000,
        )
        print("BUMP_OK counter=1")

        if scenario == "normal":
            # A fully-normal session: bump a few more + chain, expect no break.
            page.click("#bump-btn")
            page.click("#chain-btn")  # +2
            page.wait_for_timeout(800)
            counter = page.eval_on_selector("#counter", "el => el.textContent")
            print(f"NORMAL_FINAL counter={counter}")
        elif scenario == "break":
            page.click("#break-btn")
            page.wait_for_timeout(1500)
            page.screenshot(path=str(out / f"{scenario}_02_afterbreak.png"))
            # Session should now be fatal: further bumps do nothing.
            page.click("#bump-btn")
            page.click("#bump-btn")
            page.wait_for_timeout(1000)
            counter = page.eval_on_selector("#counter", "el => el.textContent")
            print(f"POSTBREAK counter={counter} (expected still 1)")
            nav_type = page.evaluate(
                "() => performance.getEntriesByType('navigation')[0].type"
            )
            print(f"NAV_TYPE={nav_type} (expected navigate; reload=bad)")
        elif scenario == "bgbreak":
            page.click("#bg-break-btn")
            page.wait_for_timeout(2000)
            page.screenshot(path=str(out / f"{scenario}_02_afterbgbreak.png"))
            page.click("#bump-btn")
            page.wait_for_timeout(800)
            counter = page.eval_on_selector("#counter", "el => el.textContent")
            print(f"BGBREAK_FINAL counter={counter}")

        browser.close()

    (out / f"{scenario}_console.log").write_text("\n".join(console_msgs))
    (out / f"{scenario}_pageerrors.log").write_text("\n".join(page_errors))
    (out / f"{scenario}_failedreqs.log").write_text("\n".join(failed_reqs))
    print(f"CONSOLE_MSGS={len(console_msgs)} PAGE_ERRORS={len(page_errors)} FAILED_REQS={len(failed_reqs)}")
    for m in console_msgs:
        print("  CONSOLE", m)
    for e in page_errors:
        print("  PAGEERR", e)
    for f in failed_reqs:
        print("  FAILREQ", f)


if __name__ == "__main__":
    main()
