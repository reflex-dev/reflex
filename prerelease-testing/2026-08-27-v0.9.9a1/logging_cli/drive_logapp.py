"""Playwright driver for the logging cluster test app.

Usage:
    $SB/envs/driver/bin/python drive_logapp.py <frontend_url> <outdir>

Drives the app as a user: clicks increment twice, runs the background task,
fires the event chain, and asserts the state text updates. Captures browser
console messages, page errors, failed/4xx+ network responses, and screenshots
into <outdir>. Prints CHECK lines (PASS/FAIL) and exits nonzero on failure.
"""

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BENIGN_CONSOLE_SNIPPETS = (
    "HydrateFallback",
    "[vite] connecting",
    "[vite] connected",
    "React DevTools",
)

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(f"{'PASS' if cond else 'FAIL'}: {name}" + (f" -- {detail}" if detail else ""))


def main():
    url = sys.argv[1]
    outdir = Path(sys.argv[2])
    outdir.mkdir(parents=True, exist_ok=True)
    console_msgs = []
    page_errors = []
    bad_responses = []
    failed_requests = []

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        page = browser.new_page()
        page.on(
            "console",
            lambda m: console_msgs.append(
                {"type": m.type, "text": m.text, "location": str(m.location)}
            ),
        )
        page.on("pageerror", lambda e: page_errors.append(str(e)))
        page.on(
            "response",
            lambda r: bad_responses.append({"url": r.url, "status": r.status})
            if r.status >= 400
            else None,
        )
        page.on(
            "requestfailed",
            lambda r: failed_requests.append({"url": r.url, "failure": r.failure}),
        )

        page.goto(url, wait_until="load", timeout=60000)
        page.wait_for_selector("#btn-inc", timeout=30000)
        # Wait for websocket state hydration: status text present.
        page.wait_for_selector("#status", timeout=30000)
        page.screenshot(path=str(outdir / "01_loaded.png"))

        page.click("#btn-inc")
        page.wait_for_function(
            "document.querySelector('#count').innerText.includes('1')", timeout=15000
        )
        page.click("#btn-inc")
        page.wait_for_function(
            "document.querySelector('#count').innerText.includes('2')", timeout=15000
        )
        check("increment updates count to 2", True)
        status_txt = page.inner_text("#status")
        check("status reflects clicks", "clicked 2" in status_txt, status_txt)
        page.screenshot(path=str(outdir / "02_after_clicks.png"))

        page.click("#btn-bg")
        page.wait_for_selector("#bg-done", timeout=20000)
        check("background task completes and cond flips", True)
        page.screenshot(path=str(outdir / "03_bg_done.png"))

        page.click("#btn-chain")
        page.wait_for_function(
            "document.querySelector('#count').innerText.includes('3')", timeout=15000
        )
        check("event chain increments count to 3", True)
        page.screenshot(path=str(outdir / "04_after_chain.png"))

        browser.close()

    (outdir / "console.json").write_text(json.dumps(console_msgs, indent=2))
    (outdir / "network_failures.json").write_text(
        json.dumps({"bad_responses": bad_responses, "failed": failed_requests}, indent=2)
    )
    (outdir / "page_errors.json").write_text(json.dumps(page_errors, indent=2))

    unexpected = [
        m
        for m in console_msgs
        if m["type"] in ("error", "warning")
        and not any(s in m["text"] for s in BENIGN_CONSOLE_SNIPPETS)
    ]
    check(
        "no unexpected browser console errors/warnings",
        not unexpected,
        json.dumps(unexpected[:5]),
    )
    check("no page errors", not page_errors, str(page_errors[:3]))
    check(
        "no failed/4xx+ network responses",
        not bad_responses and not failed_requests,
        json.dumps((bad_responses + failed_requests)[:5]),
    )

    fails = [r for r in results if not r[1]]
    print(f"DRIVER SUMMARY: {len(results) - len(fails)}/{len(results)} passed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
