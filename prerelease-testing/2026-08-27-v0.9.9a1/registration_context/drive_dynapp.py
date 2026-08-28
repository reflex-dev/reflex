"""Playwright driver for dynapp (test c): dynamic components + bundle_library.

Run (server must already be on :3420):
    <driver-venv>/bin/python drive_dynapp.py [base_url]
"""

import json
import sys
import time

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3420"
CHROMIUM = "/opt/pw-browsers/chromium"

console_msgs = []
failed_requests = []
results = []


def check(name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    results.append((status, name, detail))
    print(f"[{status}] {name} {('- ' + detail) if detail else ''}")


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
    page.on(
        "requestfailed",
        lambda r: failed_requests.append(f"{r.method} {r.url} -> {r.failure}"),
    )
    page.on(
        "response",
        lambda r: failed_requests.append(f"{r.status} {r.url}")
        if r.status >= 400
        else None,
    )

    page.goto(BASE + "/", wait_until="load", timeout=60000)
    page.wait_for_selector("#marker", timeout=60000)
    check("index renders", page.inner_text("#marker") == "DYNAPP")

    # static lucide icon renders as svg
    static_svg = wait_for(lambda: page.query_selector("#static-icon"))
    check("static lucide icon present", static_svg is not None)

    # dynamic plain-var component (radix button from state) hydrates
    dyn_btn = wait_for(lambda: page.query_selector("#dyn-button"))
    check(
        "dynamic Component state var renders",
        dyn_btn is not None and page.inner_text("#dyn-button") == "dyn-button-initial",
        f"text={page.inner_text('#dyn-button') if dyn_btn else None!r}",
    )

    # computed-var dynamic block with lucide icon inside
    dyn_label = wait_for(lambda: page.query_selector("#dyn-label"))
    check(
        "computed dynamic block renders",
        dyn_label is not None and page.inner_text("#dyn-label") == "label: start",
        f"text={page.inner_text('#dyn-label') if dyn_label else None!r}",
    )
    dyn_icon = page.query_selector("#dyn-icon")
    check("lucide icon INSIDE dynamic component renders", dyn_icon is not None)

    page.screenshot(path="dynapp_initial.png", full_page=True)

    # window.__reflex keys — what actually got bundled?
    keys = page.evaluate("() => Object.keys(window.__reflex || {})")
    print("window.__reflex keys:", json.dumps(keys))
    check(
        "window.__reflex contains radix (plugin bundle_library)",
        any("radix-ui/themes" in k for k in keys),
        str(keys),
    )
    check(
        "window.__reflex contains lucide-react (user bundle_library)",
        "lucide-react" in keys,
        "user import-time bundle_library %s survive frontend compile"
        % ("did" if "lucide-react" in keys else "did NOT"),
    )

    # event handler defined on a dynamic component works
    if page.query_selector("#dyn-relabel"):
        page.click("#dyn-relabel")
        ok = wait_for(lambda: page.inner_text("#dyn-label") == "label: clicked", timeout=15)
        check("event handler inside dynamic component works", bool(ok))

    # swapping the plain Component var via event
    page.click("#swap-btn")
    ok = wait_for(lambda: page.inner_text("#dyn-button") == "dyn-button-clicked", timeout=15)
    check("Component state var swap via event works", bool(ok))

    page.screenshot(path="dynapp_after_clicks.png", full_page=True)
    browser.close()

print("\n--- console ---")
known_benign = ("HydrateFallback", "[vite] connect", "React DevTools")
for m in console_msgs:
    tag = "" if any(b in m for b in known_benign) else "  <== UNEXPECTED?"
    print(m[:300] + tag)
print("--- failed/4xx+ requests ---")
for r in failed_requests:
    print(r[:300])
if not failed_requests:
    print("(none)")

fails = [r for r in results if r[0] == "FAIL"]
print(f"\n{len(results) - len(fails)}/{len(results)} checks passed")
sys.exit(1 if fails else 0)
