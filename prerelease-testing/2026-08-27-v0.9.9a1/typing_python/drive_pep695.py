"""Playwright driver for the PEP695 alias app on reflex 0.9.9a1.

Usage: python drive_pep695.py <frontend_url> <screenshot_dir> <server_log>

Verifies:
- initial render of every alias-annotated var shape (compile + hydration OK,
  the part PR #6944 fixed);
- documents BUG: any event handler that ASSIGNS an alias-annotated var raises
  TypeError server-side (State.__setattr__ -> _isinstance does not resolve
  TypeAliasType), so the UI never updates. This driver asserts that exact
  (buggy) behavior so a fixed reflex will make the 'bug still present' checks
  flip, flagging the fix.
"""

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

url = sys.argv[1]
shots = sys.argv[2]
server_log = Path(sys.argv[3]) if len(sys.argv) > 3 else None

console_msgs: list[str] = []
failed_requests: list[str] = []
failures: list[str] = []

BENIGN = ("HydrateFallback", "[vite]", "React DevTools", "💿")


def check(name: str, cond: bool, detail: str = ""):
    status = "PASS" if cond else "FAIL"
    print(f"{status}: {name} {detail}")
    if not cond:
        failures.append(f"{name}: {detail}")


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = browser.new_page()
    page.on(
        "console",
        lambda m: console_msgs.append(f"[{m.type}] {m.text}")
        if m.type in ("error", "warning")
        else None,
    )
    page.on("pageerror", lambda e: console_msgs.append(f"[pageerror] {e}"))
    page.on(
        "response",
        lambda r: failed_requests.append(f"{r.status} {r.url}")
        if r.status >= 400
        else None,
    )
    page.goto(url, wait_until="networkidle")
    page.wait_for_selector("#title")
    page.wait_for_function(
        "document.querySelector('#name').innerText.includes('reflex')", timeout=30000
    )
    page.screenshot(path=f"{shots}/01_loaded.png")

    check("render: plain alias var (name)", page.inner_text("#name") == "name: reflex")
    check("render: Literal alias var (key)", page.inner_text("#key") == "key: day")
    check("render: alias|None union via rx.cond", page.inner_text("#union") == "union: none")
    check("render: alias-of-alias (MaybeKey)", page.inner_text("#nested") == "nested: none")
    check(
        "render: variadic alias tuple var",
        page.inner_text("#pos").replace(" ", "") == 'pos:[7,"seven"]',
        repr(page.inner_text("#pos")),
    )
    check(
        "render: generic list alias via rx.foreach",
        page.inner_text("#entries").split() == ["alpha", "beta"],
        repr(page.inner_text("#entries")),
    )
    check(
        "render: generic dict alias via rx.foreach",
        "alpha=1" in page.inner_text("#scores")
        and "beta=2" in page.inner_text("#scores"),
        repr(page.inner_text("#scores")),
    )

    # BUG documentation: assignment to alias-annotated var crashes server-side.
    before_errors = (
        server_log.read_text().count("isinstance() arg 2 must be a type")
        if server_log
        else 0
    )
    page.click("#btn-week")
    time.sleep(4)
    check(
        "BUG still present: click does NOT update key (alias setattr TypeError)",
        page.inner_text("#key") == "key: day",
        repr(page.inner_text("#key")),
    )
    if server_log:
        after_errors = server_log.read_text().count(
            "isinstance() arg 2 must be a type"
        )
        check(
            "BUG still present: server log gained isinstance TypeError",
            after_errors > before_errors,
            f"before={before_errors} after={after_errors}",
        )

    page.fill("#entry-input", "gamma")
    page.click("#entry-submit")
    time.sleep(4)
    check(
        "BUG still present: form submit does NOT add entry",
        "gamma" not in page.inner_text("#entries"),
        repr(page.inner_text("#entries")),
    )

    page.screenshot(path=f"{shots}/02_after_clicks_no_update.png")
    browser.close()

unexpected_console = [m for m in console_msgs if not any(b in m for b in BENIGN)]
print("\n--- unexpected console messages ---")
for m in unexpected_console:
    print(m)
print("--- failed requests ---")
for r in failed_requests:
    print(r)
print(f"\nRESULT: {'FAIL' if failures else 'PASS (render OK, known bug behavior confirmed)'}")
sys.exit(1 if failures else 0)
