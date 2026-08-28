"""Playwright driver for the builtins-annotation busy app (PR #6890/#6896).

Usage: python drive_busy.py <frontend_url> <screenshot_dir> [upload_file]

Drives every handler: dict/list/set/tuple/bool/str payloads, background task,
event chain, and a file upload (list[rx.UploadFile] annotation resolution).
"""

import sys
import time

from playwright.sync_api import sync_playwright

url = sys.argv[1]
shots = sys.argv[2]
upload_file = sys.argv[3] if len(sys.argv) > 3 else None

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
        "document.querySelector('#count').innerText.includes('0')", timeout=30000
    )
    page.screenshot(path=f"{shots}/01_loaded.png")

    def log_text() -> str:
        return page.inner_text("#log")

    page.click("#b-dict")
    page.wait_for_function(
        "document.querySelector('#log').innerText.includes('dict:2')", timeout=10000
    )
    check("dict payload handler", '"a":1' in page.inner_text("#data").replace(" ", ""),
          repr(page.inner_text("#data")))

    page.click("#b-tdict")
    page.wait_for_function(
        "document.querySelector('#log').innerText.includes('tdict:1')", timeout=10000
    )
    check("dict[str,int] payload handler", '"x":10' in page.inner_text("#tdata").replace(" ", ""),
          repr(page.inner_text("#tdata")))

    page.click("#b-list")
    page.wait_for_function(
        "document.querySelector('#log').innerText.includes('list:3')", timeout=10000
    )
    check("list payload handler", '"p"' in page.inner_text("#tags"), repr(page.inner_text("#tags")))

    page.click("#b-tlist")
    page.wait_for_function(
        "document.querySelector('#log').innerText.includes('tlist:2')", timeout=10000
    )
    check("list[str] payload handler", '"s"' in page.inner_text("#ttags"), repr(page.inner_text("#ttags")))

    page.click("#b-set")
    time.sleep(3)
    set_log = [line for line in log_text().splitlines() if line.startswith("set:")]
    check("set payload handler ran", bool(set_log), f"log lines: {log_text()!r}")
    if set_log:
        print(f"INFO : set payload arrived as -> {set_log[0]!r}")

    page.click("#b-tuple")
    time.sleep(2)
    tuple_log = [line for line in log_text().splitlines() if line.startswith("tuple:")]
    check("tuple payload handler ran", bool(tuple_log), f"log lines: {log_text()!r}")
    if tuple_log:
        print(f"INFO : tuple payload arrived as -> {tuple_log[0]!r}")

    page.click("#b-bg")
    page.wait_for_function(
        "document.querySelector('#count').innerText.includes('5')", timeout=10000
    )
    check("background task dict payload", True)

    page.click("#cb-ok")
    page.wait_for_function(
        "document.querySelector('#ok').innerText.includes('true')", timeout=10000
    )
    check("checkbox bool payload", True)

    page.fill("#in-str", "hey")
    page.wait_for_function(
        "document.querySelector('#log').innerText.includes('str:hey')", timeout=10000
    )
    check("str payload + event chain (yield take_bool)", "bool:True" in log_text(), repr(log_text()))

    if upload_file:
        page.set_input_files("input[type='file']", upload_file)
        page.wait_for_function(
            "document.querySelector('#log').innerText.includes('upload:')",
            timeout=15000,
        )
        upload_line = [
            line for line in log_text().splitlines() if line.startswith("upload:")
        ]
        check("upload handler (list[rx.UploadFile])", bool(upload_line),
              upload_line[0] if upload_line else "")

    page.screenshot(path=f"{shots}/02_after_interactions.png")
    browser.close()

unexpected_console = [m for m in console_msgs if not any(b in m for b in BENIGN)]
print("\n--- unexpected console messages ---")
for m in unexpected_console:
    print(m)
print("--- failed requests ---")
for r in failed_requests:
    print(r)
print(f"\nRESULT: {'FAIL' if failures else 'PASS'}")
sys.exit(1 if failures else 0)
