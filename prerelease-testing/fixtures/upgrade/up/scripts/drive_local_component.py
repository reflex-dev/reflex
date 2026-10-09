"""Drive the reflex-examples `local-component` app (local React component via rx.asset(shared=True)).

Usage: drive_local_component.py <url> <outdir> <tag>
Flows: Hello renders, id/title/background_color pass through forwardRef, right-click toggles the
component's own useState AND fires rx.console_log(...).prevent_default, popover open (State.open),
live typing (State.who), form submit + close, reopen + Escape reverts, rx.scroll_to("greeting"),
color-mode toggle switches rx.color_mode_cond background, reload keeps state + color mode.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from harness import CHROMIUM, Run, guard_driver_python  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

guard_driver_python()
URL, OUT, TAG = sys.argv[1:4]
run = Run(TAG, OUT)
LIGHT, DARK = "rgb(255, 239, 213)", "rgb(102, 51, 153)"


def pump(page, cond, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if cond():
                return True
        except Exception:  # noqa: BLE001
            pass
        page.wait_for_timeout(150)
    return bool(cond())


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM)
    ctx = browser.new_context(viewport={"width": 1280, "height": 900}, color_scheme="light")
    page = ctx.new_page()
    run.attach(page, "main")
    page.goto(URL, wait_until="load")
    g = page.locator("#greeting")
    g.wait_for(timeout=60000)
    h1 = g.locator("h1")
    txt = lambda: h1.inner_text()  # noqa: E731
    bg = lambda: g.evaluate("el => getComputedStyle(el).backgroundColor")  # noqa: E731
    pump(page, lambda: txt() == "Hello world!", 10)
    run.check("1: local Hello component renders 'Hello world!'", txt() == "Hello world!", txt())
    run.check("2: id reaches the DOM node through forwardRef (single #greeting div)", g.count() == 1 and g.evaluate("e => e.tagName") == "DIV", g.count())
    run.check("3: title passes through", g.get_attribute("title") == "Click to change name. Right-click to toggle caps.", g.get_attribute("title"))
    run.check("4: background_color (rx.color_mode_cond) light", bg() == LIGHT, bg())
    run.shot(page, "01_initial")
    n0 = len(run.console)
    h1.click(button="right")
    ok = pump(page, lambda: txt() == "HELLO WORLD!", 5)
    page.wait_for_timeout(300)
    logged = any("Yes we pass events through" in m["text"] for m in run.console[n0:])
    run.check("5: right-click toggles useState caps AND fires rx.console_log passthrough", ok and logged, f"text={txt()} logged={logged}")
    h1.click(button="right")
    run.check("6: second right-click toggles back", pump(page, lambda: txt() == "Hello world!", 5), txt())
    h1.click()
    inp = page.locator("input[name='who']")
    ok = pump(page, lambda: inp.count() == 1 and inp.is_visible(), 6)
    run.check("7: left-click opens the popover (State.open)", ok, inp.count())
    run.shot(page, "02_popover")
    inp.fill("")
    inp.type("Reflex QA", delay=40)
    ok = pump(page, lambda: txt() == "Hello Reflex QA!", 6)
    run.check("8: typing live-updates the greeting (State.who -> name prop)", ok, txt())
    inp.press("Enter")
    ok = pump(page, lambda: page.locator("input[name='who']").count() == 0 or not page.locator("input[name='who']").is_visible(), 6)
    page.wait_for_timeout(500)
    run.check("9: Enter submits the form, popover closes, value kept", ok and txt() == "Hello Reflex QA!", txt())
    h1.click()
    ok = pump(page, lambda: page.locator("input[name='who']").count() == 1 and page.locator("input[name='who']").is_visible(), 6)
    if ok:
        page.locator("input[name='who']").fill("")
        page.locator("input[name='who']").type("THROWAWAY", delay=30)
        pump(page, lambda: txt() == "Hello THROWAWAY!", 6)
        mid = txt()
        page.keyboard.press("Escape")
        ok2 = pump(page, lambda: txt() == "Hello Reflex QA!", 6)
        run.check("10: reopen + type + Escape reverts to the saved value", mid == "Hello THROWAWAY!" and ok2, f"{mid} -> {txt()}")
    else:
        run.check("10: reopen popover", False, "did not reopen")
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(600)
    y0 = page.evaluate("window.scrollY")
    page.get_by_role("button", name="Scroll to Greeting").click()
    ok = pump(page, lambda: page.evaluate("window.scrollY") < y0 - 100, 5)
    page.wait_for_timeout(600)
    y1 = page.evaluate("window.scrollY")
    run.check("11: rx.scroll_to('greeting') scrolls back up", ok, f"scrollY {y0} -> {y1}")
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(400)
    page.locator("button.rt-IconButton").first.click()
    ok = pump(page, lambda: bg() == DARK, 5)
    run.check("12: color-mode button flips rx.color_mode_cond background to dark", ok, bg())
    run.shot(page, "03_dark")
    page.reload(wait_until="load")
    page.locator("#greeting h1").wait_for(timeout=30000)
    ok = pump(page, lambda: page.locator("#greeting h1").inner_text() == "Hello Reflex QA!", 10)
    bg2 = page.locator("#greeting").evaluate("el => getComputedStyle(el).backgroundColor")
    run.check("13: reload keeps State.who (saved) and the color mode", ok and bg2 == DARK, f"text={page.locator('#greeting h1').inner_text()} bg={bg2}")
    run.shot(page, "04_reload")
    # the compiled module that imports the local .jsx
    mods = page.evaluate("() => performance.getEntriesByType('resource').map(e => e.name).filter(n => n.includes('hello'))")
    run.notes["hello_resources"] = mods
    browser.close()
sys.exit(run.finish())
