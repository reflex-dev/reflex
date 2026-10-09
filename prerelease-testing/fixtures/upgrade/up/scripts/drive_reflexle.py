"""Drive reflex-examples reflexle (wordle; reflex-global-hotkey, @rx.memo, rx.toast, bg task).

Usage: drive_reflexle.py <url> <outdir> <tag>
Real keyboard input via Playwright -> global_hotkey_watcher -> backend; checks tile echo,
colouring after Enter, keyboard-button recolour, short-guess toast, invalid word shake +
background-task auto-clear, Backspace, on-screen key clicks, high-contrast + colour-mode
toggles, play-again reset, post-reset guess, reload (state survives same token), and a
second browser context (independent game).
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from harness import CHROMIUM, Run, guard_driver_python, wait_for  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

guard_driver_python()
URL, OUT, TAG = sys.argv[1:4]
run = Run(TAG, OUT)

GRID_JS = """
() => {
  const rows = [];
  for (const div of document.querySelectorAll('div')) {
    const kids = Array.from(div.children);
    if (kids.length === 5 && kids.every(k => k.tagName === 'DIV'
        && k.children.length === 1 && k.children[0].tagName === 'DIV'
        && k.children[0].textContent.length <= 1)) {
      rows.push(kids.map(k => ({letter: k.textContent, bg: getComputedStyle(k).backgroundColor})));
    }
  }
  return rows;
}
"""
COLORED = {
    "rgb(83, 141, 78)": "CORRECT", "rgb(181, 159, 59)": "WRONG_POSITION",
    "rgba(170, 170, 170, 0.25)": "INCORRECT", "rgb(245, 121, 58)": "CORRECT_HC",
    "rgb(133, 192, 249)": "WRONG_POSITION_HC",
}
TRANSPARENT = ("rgba(0, 0, 0, 0)", "transparent")


def grid(page):
    return page.evaluate(GRID_JS)


def row_word(row):
    return "".join(t["letter"] for t in row)


def typed(page, word, delay=0.2):
    for ch in word:
        page.keyboard.press(ch)
        time.sleep(delay)


def click_key(page, text):
    page.evaluate("""(l) => { for (const b of document.querySelectorAll('button')) {
        if (b.textContent === l) { b.click(); return; } } }""", text)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM)
    ctx = browser.new_context(viewport={"width": 1000, "height": 900})
    page = ctx.new_page()
    run.attach(page)
    page.goto(URL, wait_until="load", timeout=60000)
    page.wait_for_selector("text=Reflexle", timeout=40000)
    g = wait_for(lambda: (lambda x: x if len(x) == 6 else None)(grid(page)), 25)
    run.check("load: grid renders 6x5", bool(g), f"rows={len(g) if g else None}")
    if g:
        run.check("load: grid initially blank",
                  all(t["letter"] == " " and t["bg"] in TRANSPARENT for r in g for t in r))
    run.shot(page, "01_initial")

    def key_registered():
        page.keyboard.press("c")
        time.sleep(0.5)
        return grid(page)[0][0]["letter"] == "c"

    ok = wait_for(key_registered, 25, 0.1)
    run.check("hotkey: keydown reaches backend state", bool(ok))
    for _ in range(5):
        page.keyboard.press("Backspace")
        time.sleep(0.15)
    wait_for(lambda: row_word(grid(page)[0]) == "     ", 5)
    typed(page, "crane")
    ok = wait_for(lambda: row_word(grid(page)[0]) == "crane", 5)
    run.check("type 'crane': tiles echo letters", bool(ok), row_word(grid(page)[0]))
    page.keyboard.press("Enter")
    r0 = wait_for(lambda: (lambda r: r if all(t["bg"] in COLORED for t in r) else None)(grid(page)[0]), 10)
    run.check("submit guess: row0 coloured", bool(r0),
              json.dumps([(t["letter"], COLORED.get(t["bg"], t["bg"])) for t in grid(page)[0]]))
    run.shot(page, "02_guess1")
    kb = wait_for(lambda: page.evaluate("""() => { for (const b of document.querySelectorAll('button'))
        if (b.textContent === 'c') return getComputedStyle(b).backgroundColor; return null; }""")
        not in (None, "rgba(170, 170, 170, 0.5)"), 5)
    run.check("on-screen keyboard recoloured after guess", bool(kb))
    typed(page, "zz", 0.15)
    page.keyboard.press("Enter")
    try:
        page.wait_for_selector("text=Word must be 5 characters long.", timeout=6000)
        run.check("short guess: rx.toast shown", True)
    except Exception as e:  # noqa: BLE001
        run.check("short guess: rx.toast shown", False, e)
    run.shot(page, "03_toast")
    for _ in range(2):
        page.keyboard.press("Backspace")
        time.sleep(0.15)
    typed(page, "zzzzz", 0.15)
    page.keyboard.press("Enter")
    shaken = wait_for(lambda: row_word(grid(page)[1]) == "zzzzz", 2, 0.05)
    cleared = wait_for(lambda: row_word(grid(page)[1]) == "     ", 6)
    run.check("invalid word: background task auto-clears row", bool(cleared),
              f"seen-before-clear={bool(shaken)} row1={row_word(grid(page)[1])!r}")
    typed(page, "ab", 0.15)
    page.keyboard.press("Backspace")
    ok = wait_for(lambda: row_word(grid(page)[1]) == "a    ", 5)
    run.check("Backspace removes last letter", bool(ok), row_word(grid(page)[1]))
    page.keyboard.press("Backspace")
    time.sleep(0.4)
    click_key(page, "q")
    ok = wait_for(lambda: row_word(grid(page)[1]) == "q    ", 5)
    run.check("on-screen key click types letter (@rx.memo keyboard_button)", bool(ok), row_word(grid(page)[1]))
    click_key(page, "⌫")
    ok = wait_for(lambda: row_word(grid(page)[1]) == "     ", 5)
    run.check("on-screen backspace click", bool(ok))
    had = any(COLORED.get(t["bg"]) in ("CORRECT", "WRONG_POSITION") for t in grid(page)[0])
    page.click("button:has(svg.lucide-contrast)")
    if had:
        ok = wait_for(lambda: any(COLORED.get(t["bg"], "").endswith("_HC") for t in grid(page)[0]), 5)
        run.check("high-contrast toggle recolours tiles", bool(ok))
    else:
        run.check("high-contrast toggle recolours tiles", "skipped", "no green/yellow in guess")
    run.shot(page, "04_hc")
    page.click("button:has(svg.lucide-contrast)")
    time.sleep(0.3)
    before = page.evaluate("() => document.documentElement.className")
    page.click("button:has(svg.lucide-moon), button:has(svg.lucide-sun)")
    ok = wait_for(lambda: page.evaluate("() => document.documentElement.className") != before, 5)
    run.check("colour-mode toggle flips theme", bool(ok),
              f"{before!r} -> {page.evaluate('() => document.documentElement.className')!r}")
    page.click("button:has(svg.lucide-moon), button:has(svg.lucide-sun)")
    time.sleep(0.3)
    # reload: the game (backend _word + guesses) should survive on the same tab token
    page.reload(wait_until="load")
    page.wait_for_selector("text=Reflexle", timeout=30000)
    ok = wait_for(lambda: row_word(grid(page)[0]) == "crane", 15)
    run.check("reload: guess 'crane' survives (same session token, on_load keeps game)", bool(ok),
              row_word(grid(page)[0]) if grid(page) else None)
    run.shot(page, "05_after_reload")
    # second browser context = independent game
    ctx2 = browser.new_context(viewport={"width": 1000, "height": 900})
    p2 = ctx2.new_page()
    run.attach(p2, "ctx2")
    p2.goto(URL, wait_until="load")
    p2.wait_for_selector("text=Reflexle", timeout=30000)
    g2 = wait_for(lambda: (lambda x: x if len(x) == 6 else None)(grid(p2)), 20)
    run.check("second context: independent blank game", bool(g2) and row_word(g2[0]) == "     ",
              row_word(g2[0]) if g2 else None)
    ctx2.close()
    page.click("button:has(svg.lucide-refresh-cw)")
    ok = wait_for(lambda: all(t["letter"] == " " for r in grid(page) for t in r), 5)
    run.check("play-again resets grid", bool(ok))
    page.keyboard.press("Escape")
    typed(page, "slate")
    page.keyboard.press("Enter")
    r0 = wait_for(lambda: (lambda r: r if all(t["bg"] in COLORED for t in r) else None)(grid(page)[0]), 10)
    run.check("post-reset guess coloured", bool(r0),
              json.dumps([(t["letter"], COLORED.get(t["bg"], t["bg"])) for t in grid(page)[0]]))
    run.shot(page, "06_final")
    browser.close()

sys.exit(run.finish())
