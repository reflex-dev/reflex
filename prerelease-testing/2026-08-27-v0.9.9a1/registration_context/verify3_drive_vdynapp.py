"""Playwright driver: verify window.__reflex contents + module-specifier errors.

Usage: <driver-venv>/bin/python drive_vdynapp.py http://localhost:3932
"""

import json
import sys
import time

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3932"
CHROMIUM = "/opt/pw-browsers/chromium"

console_msgs = []


def wait_for(fn, timeout=30, interval=0.25):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            last = fn()
            if last:
                return last
        except Exception:  # noqa: BLE001
            pass
        time.sleep(interval)
    return last


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM)
    page = browser.new_page()
    page.on("console", lambda m: console_msgs.append(f"[{m.type}] {m.text}"))
    page.on("pageerror", lambda e: console_msgs.append(f"[pageerror] {e}"))

    page.goto(BASE + "/", wait_until="load", timeout=120000)
    page.wait_for_selector("#marker", timeout=120000)
    print("index rendered:", page.inner_text("#marker"))

    static_icon = wait_for(lambda: page.query_selector("#static-icon"), timeout=20)
    print("static icon present:", static_icon is not None)

    dyn_label = wait_for(lambda: page.query_selector("#dyn-label"), timeout=25)
    print("computed dynamic block rendered:", dyn_label is not None)

    keys = page.evaluate("() => Object.keys(window.__reflex || {})")
    print("window.__reflex keys:", json.dumps(keys))
    print("CHECK lucide-react in window.__reflex:", "lucide-react" in keys)

    page.screenshot(path="vdynapp.png", full_page=True)
    browser.close()

print("\n--- console (specifier/module errors only) ---")
hits = [m for m in console_msgs if "module specifier" in m or "lucide" in m]
for m in hits:
    print(m[:400])
print(f"({len(hits)} matching console messages of {len(console_msgs)} total)")
print("\nCHECK 'Failed to resolve module specifier' seen:", any("Failed to resolve module specifier" in m for m in console_msgs))
