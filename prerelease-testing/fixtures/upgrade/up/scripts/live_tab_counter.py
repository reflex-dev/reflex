"""Counter tab open while the venv is upgraded UNDER a running `reflex run` (dev).

Usage: live_tab_counter.py <url> <outdir> <tag> <ctldir>
Waits for <ctldir>/edited (operator: venv upgraded in place, then an app file touched so
hot reload imports the new reflex), then records what the tab shows and whether
Increment still works, before and after a manual reload.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from harness import CHROMIUM, Run, guard_driver_python, wait_for  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

guard_driver_python()
URL, OUT, TAG, CTL = sys.argv[1:5]
CTL = Path(CTL)
run = Run(TAG, OUT)


def count(page):
    try:
        return page.locator(".rt-Heading").first.inner_text().strip()
    except Exception:  # noqa: BLE001
        return None


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM)
    page = browser.new_context().new_page()
    run.attach(page)
    page.goto(URL, wait_until="load")
    page.get_by_role("button", name="Increment").wait_for(timeout=40000)
    page.evaluate("() => { window.__qa_marker = 'before-upgrade'; }")
    for _ in range(3):
        page.get_by_role("button", name="Increment").click()
    ok = wait_for(lambda: count(page) == "3", 6)
    run.check("A: counter at 3 on 0.9.12", bool(ok), count(page))
    (CTL / "ready").write_text("1")
    end = time.time() + 1800
    while not (CTL / "edited").exists() and time.time() < end:
        page.wait_for_timeout(500)
    run.notes["t_edited"] = run._t()
    page.wait_for_timeout(45000)
    info = {"marker": page.evaluate("() => window.__qa_marker || null"), "count": count(page),
            "toasts": page.locator("[data-sonner-toast]").all_inner_texts(),
            "body": page.inner_text("body")[:300]}
    run.notes["B_after_hot_reload"] = info
    run.shot(page, "B_after_hot_reload")
    print("B", info, flush=True)
    before = count(page)
    try:
        page.get_by_role("button", name="Increment").click(timeout=5000)
        ok = wait_for(lambda: count(page) not in (None, before), 8)
        run.check("B: Increment works after hot reload onto the new reflex", bool(ok), f"{before} -> {count(page)}")
    except Exception as e:  # noqa: BLE001
        run.check("B: Increment works after hot reload onto the new reflex", False, e)
    page.reload(wait_until="load")
    page.wait_for_timeout(5000)
    info = {"count": count(page), "toasts": page.locator("[data-sonner-toast]").all_inner_texts(),
            "body": page.inner_text("body")[:300]}
    run.notes["C_after_reload"] = info
    run.shot(page, "C_after_reload")
    print("C", info, flush=True)
    before = count(page)
    try:
        page.get_by_role("button", name="Increment").click(timeout=5000)
        ok = wait_for(lambda: count(page) not in (None, before), 8)
        run.check("C: Increment works after manual reload", bool(ok), f"{before} -> {count(page)}")
    except Exception as e:  # noqa: BLE001
        run.check("C: Increment works after manual reload", False, e)
    browser.close()
(CTL / "done").write_text("1")
sys.exit(run.finish())
