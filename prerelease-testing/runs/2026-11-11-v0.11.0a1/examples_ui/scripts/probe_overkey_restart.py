"""TP-04 / examples#324 probe: overkey Restart clicked MID-GAME (timer running) -- is the typed client-state input kept?

Usage: probe_overkey_restart.py <url> <outdir> <tag>
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "up" / "scripts"))
from harness import CHROMIUM, Run, guard_driver_python, wait_for  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

guard_driver_python()
URL, OUT, TAG = sys.argv[1:4]
run = Run(TAG, OUT)
LET = "() => [...document.querySelectorAll('#words .letter')].map(d => getComputedStyle(d).opacity)"
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROMIUM)
    page = b.new_page()
    run.attach(page)
    page.goto(URL)
    wait_for(lambda: len(page.evaluate(LET)) > 50, 60)
    para = page.evaluate("() => [...document.querySelectorAll('#words .letter')].map(d => d.textContent).join('')")
    page.locator("input").first.focus()
    page.keyboard.type(para[:8], delay=25)
    ok = wait_for(lambda: page.locator("button:has(svg.lucide-rotate-ccw)").count() == 1, 5)
    time.sleep(1.2)
    page.locator("button:has(svg.lucide-rotate-ccw)").first.click()
    wait_for(lambda: page.get_by_role("combobox").count() == 2, 8)
    time.sleep(1.5)
    iv = page.locator("input").first.evaluate("e => e.value")
    ib = sum(1 for o in page.evaluate(LET) if o == "1")
    run.notes["after_midgame_restart"] = {"input": iv, "in_bounds": ib}
    run.check("mid-game restart clears typed input (examples#324)", "pass" if iv == "" and ib == 0 else "anomaly",
              {"input": iv, "in_bounds": ib})
    run.shot(page, "midgame_restart")
    # type again: does the timer start (on_key_down checks value == "")?
    page.locator("input").first.focus()
    page.keyboard.type("x", delay=25)
    started = wait_for(lambda: page.locator("button:has(svg.lucide-rotate-ccw)").count() == 1, 4)
    run.check("typing after restart starts a new timer", bool(started), page.locator("input").first.evaluate("e => e.value"))
    b.close()
sys.exit(run.finish())
