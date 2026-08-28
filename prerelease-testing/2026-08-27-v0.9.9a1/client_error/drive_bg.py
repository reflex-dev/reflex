"""Focused bgbreak observer: click bg-then-break, poll up to 10s for the
frontend mismatch console error and for the fatal flag to take effect.

Usage: python drive_bg.py <frontend_url> <out_dir>
"""

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

CHROMIUM = "/opt/pw-browsers/chromium"


def main():
    url = sys.argv[1]
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    console_msgs = []
    mismatch_seen = {"t": None}
    t0 = time.time()

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM, headless=True)
        page = browser.new_page()

        def on_console(m):
            console_msgs.append(f"[{m.type}] {m.text}")
            if "Cannot process state update" in m.text and mismatch_seen["t"] is None:
                mismatch_seen["t"] = time.time() - t0

        page.on("console", on_console)
        page.goto(url, wait_until="networkidle")
        page.wait_for_function(
            "() => { const t = document.querySelector('#token'); return t && t.value; }",
            timeout=30000,
        )
        page.click("#bump-btn")
        page.wait_for_function(
            "() => document.querySelector('#counter').textContent === '1'", timeout=10000
        )
        print("BUMP_OK counter=1")

        t0 = time.time()
        page.click("#bg-break-btn")
        # Poll up to 10s for the mismatch console error.
        deadline = time.time() + 10
        while time.time() < deadline and mismatch_seen["t"] is None:
            page.wait_for_timeout(200)
        counter_after_bg = page.eval_on_selector("#counter", "el => el.textContent")
        print(f"AFTER_BG_WAIT counter={counter_after_bg} mismatch_at={mismatch_seen['t']}")

        # Now try a bump: if fatal, it stays; else it increments.
        before = page.eval_on_selector("#counter", "el => el.textContent")
        page.click("#bump-btn")
        page.wait_for_timeout(1200)
        after = page.eval_on_selector("#counter", "el => el.textContent")
        print(f"POST_BG_BUMP before={before} after={after} (equal => fatal/blocked)")
        page.screenshot(path=str(out / "bgbreak_focus.png"))
        browser.close()

    (out / "bgbreak_focus_console.log").write_text("\n".join(console_msgs))
    mism = [m for m in console_msgs if "Cannot process state update" in m]
    print(f"MISMATCH_CONSOLE_COUNT={len(mism)}")
    for m in mism:
        print("  ", m)


if __name__ == "__main__":
    main()
