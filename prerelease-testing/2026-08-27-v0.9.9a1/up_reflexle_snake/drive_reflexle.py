"""Playwright driver for the reflexle example app (wordle clone).

Usage: python drive_reflexle.py <frontend_url> <outdir> <tag>

Exercises real keyboard input through reflex-global-hotkey, on-screen keyboard
clicks, invalid-word toast, backspace editing, high-contrast toggle and game
reset.  Writes screenshots + <tag>_results.json + <tag>_console.json to outdir.
"""

import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

URL, OUTDIR, TAG = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
OUTDIR.mkdir(parents=True, exist_ok=True)

results = []
console_msgs = []
page_errors = []
bad_responses = []

GRID_JS = """
() => {
  const rows = [];
  for (const div of document.querySelectorAll('div')) {
    const kids = Array.from(div.children);
    if (kids.length === 5 && kids.every(k => k.tagName === 'DIV'
        && k.children.length === 1 && k.children[0].tagName === 'DIV'
        && k.children[0].textContent.length <= 1)) {
      rows.push(kids.map(k => ({
        letter: k.textContent,
        bg: getComputedStyle(k).backgroundColor,
      })));
    }
  }
  return rows;
}
"""

COLORED = {
    "rgb(83, 141, 78)": "CORRECT",
    "rgb(181, 159, 59)": "WRONG_POSITION",
    "rgba(170, 170, 170, 0.25)": "INCORRECT",
    "rgb(245, 121, 58)": "CORRECT_HC",
    "rgb(133, 192, 249)": "WRONG_POSITION_HC",
}
TRANSPARENT = ("rgba(0, 0, 0, 0)", "transparent")


def record(step, status, detail=""):
    results.append({"step": step, "status": status, "detail": detail})
    print(f"[{status.upper():7}] {step}: {detail}", flush=True)


def grid(page):
    return page.evaluate(GRID_JS)


def row_word(row):
    return "".join(t["letter"] for t in row)


def wait_for(fn, timeout=10.0, interval=0.25):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            v = fn()
            if v:
                return v
        except Exception:
            pass
        time.sleep(interval)
    return None


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = browser.new_page(viewport={"width": 1000, "height": 900})
    page.on("console", lambda m: console_msgs.append({"type": m.type, "text": m.text}))
    page.on("pageerror", lambda e: page_errors.append(str(e)))
    page.on(
        "response",
        lambda r: bad_responses.append({"url": r.url, "status": r.status})
        if r.status >= 400
        else None,
    )
    page.on(
        "requestfailed",
        lambda r: bad_responses.append({"url": r.url, "failure": r.failure}),
    )

    page.goto(URL, wait_until="load", timeout=60000)
    page.wait_for_selector("text=Reflexle", timeout=30000)
    g = wait_for(lambda: (lambda x: x if len(x) == 6 else None)(grid(page)), 20)
    record(
        "load: grid renders 6 rows x 5 tiles",
        "pass" if g else "fail",
        f"rows={len(g) if g else 'none'}",
    )
    page.screenshot(path=str(OUTDIR / f"{TAG}_01_initial.png"))

    if g:
        blank = all(t["letter"] == " " and t["bg"] in TRANSPARENT for r in g for t in r)
        record("load: grid initially blank", "pass" if blank else "anomaly", json.dumps(g[0]))

    # Warm up: wait until keystrokes round-trip through the websocket.
    def key_registered():
        page.keyboard.press("c")
        time.sleep(0.5)
        return grid(page)[0][0]["letter"] == "c"

    ok = wait_for(key_registered, 25, 0.1)
    record("hotkey: keydown reaches backend state", "pass" if ok else "fail")
    for _ in range(5):
        page.keyboard.press("Backspace")
        time.sleep(0.15)

    # Type a real guess.
    for ch in "crane":
        page.keyboard.press(ch)
        time.sleep(0.2)
    time.sleep(0.6)
    g = grid(page)
    record(
        "type 'crane': tiles echo letters",
        "pass" if row_word(g[0]) == "crane" else "fail",
        f"row0={row_word(g[0])!r}",
    )
    page.screenshot(path=str(OUTDIR / f"{TAG}_02_typed.png"))

    # Submit and wait for coloring (transition delay up to 1.5s).
    page.keyboard.press("Enter")

    def row0_colored():
        r = grid(page)[0]
        return all(t["bg"] in COLORED for t in r) and r

    r0 = wait_for(row0_colored, 10)
    g = grid(page)
    record(
        "submit guess: row0 tiles colored",
        "pass" if r0 else "fail",
        json.dumps([(t["letter"], COLORED.get(t["bg"], t["bg"])) for t in g[0]]),
    )
    page.screenshot(path=str(OUTDIR / f"{TAG}_03_guess1_colored.png"))

    # On-screen keyboard buttons reflect guessed-letter correctness.
    def key_button_bg(letter):
        return page.evaluate(
            """(l) => {
              for (const b of document.querySelectorAll('button')) {
                if (b.textContent === l) return getComputedStyle(b).backgroundColor;
              }
              return null;
            }""",
            letter,
        )

    kb_bg = wait_for(
        lambda: (lambda bg: bg if bg and bg != "rgba(170, 170, 170, 0.5)" else None)(
            key_button_bg("c")
        ),
        5,
    )
    record(
        "keyboard buttons recolored after guess",
        "pass" if kb_bg else "anomaly",
        f"key 'c' bg={kb_bg or key_button_bg('c')}",
    )

    # Short guess -> toast (the only toast path that is actually reachable:
    # received_letter discards the rx.toast returned by ReflexleGame.guess).
    for ch in "zz":
        page.keyboard.press(ch)
        time.sleep(0.15)
    page.keyboard.press("Enter")
    try:
        page.wait_for_selector("text=Word must be 5 characters long.", timeout=5000)
        record("short guess: toast shown", "pass")
    except Exception:
        record("short guess: toast shown", "fail", "no toast in 5s")
    page.screenshot(path=str(OUTDIR / f"{TAG}_04_short_toast.png"))
    for _ in range(2):
        page.keyboard.press("Backspace")
        time.sleep(0.15)

    # Invalid 5-letter word -> shake animation + auto-clear via background task.
    for ch in "zzzzz":
        page.keyboard.press(ch)
        time.sleep(0.15)
    page.keyboard.press("Enter")
    cleared = wait_for(lambda: row_word(grid(page)[1]) == "     ", 5)
    record(
        "invalid word: guess auto-cleared (background task)",
        "pass" if cleared else "fail",
        f"row1={row_word(grid(page)[1])!r}",
    )

    # Backspace editing.
    for ch in "ab":
        page.keyboard.press(ch)
        time.sleep(0.15)
    page.keyboard.press("Backspace")
    ok = wait_for(lambda: row_word(grid(page)[1]) == "a    ", 5)
    record("backspace removes last letter", "pass" if ok else "fail",
           f"row1={row_word(grid(page)[1])!r}")
    page.keyboard.press("Backspace")
    time.sleep(0.4)

    # On-screen keyboard click path.
    page.evaluate(
        """() => { for (const b of document.querySelectorAll('button')) {
             if (b.textContent === 'q') { b.click(); return; } } }"""
    )
    ok = wait_for(lambda: row_word(grid(page)[1]) == "q    ", 5)
    record("on-screen key click types letter", "pass" if ok else "fail",
           f"row1={row_word(grid(page)[1])!r}")
    page.evaluate(
        """() => { for (const b of document.querySelectorAll('button')) {
             if (b.textContent === '⌫') { b.click(); return; } } }"""
    )
    ok = wait_for(lambda: row_word(grid(page)[1]) == "     ", 5)
    record("on-screen backspace click clears letter", "pass" if ok else "fail")

    # High-contrast toggle.
    had_colored = any(
        COLORED.get(t["bg"]) in ("CORRECT", "WRONG_POSITION") for t in grid(page)[0]
    )
    page.click("button:has(svg.lucide-contrast)")
    if had_colored:
        ok = wait_for(
            lambda: any(
                COLORED.get(t["bg"], "").endswith("_HC") for t in grid(page)[0]
            ),
            5,
        )
        record("high-contrast toggle recolors tiles", "pass" if ok else "fail",
               json.dumps([COLORED.get(t["bg"], t["bg"]) for t in grid(page)[0]]))
    else:
        record("high-contrast toggle recolors tiles", "skipped",
               "guess had no green/yellow tiles")
    page.screenshot(path=str(OUTDIR / f"{TAG}_05_high_contrast.png"))
    page.click("button:has(svg.lucide-contrast)")
    time.sleep(0.3)

    # Color mode toggle.
    before = page.evaluate("() => document.documentElement.className")
    page.click("button:has(svg.lucide-moon), button:has(svg.lucide-sun)")
    ok = wait_for(
        lambda: page.evaluate("() => document.documentElement.className") != before, 5
    )
    after = page.evaluate("() => document.documentElement.className")
    record("color mode toggle flips theme class", "pass" if ok else "fail",
           f"{before!r} -> {after!r}")
    page.click("button:has(svg.lucide-moon), button:has(svg.lucide-sun)")
    time.sleep(0.3)

    # Reset game.
    page.click("button:has(svg.lucide-refresh-cw)")
    ok = wait_for(
        lambda: all(t["letter"] == " " for r in grid(page) for t in r), 5
    )
    record("play-again resets grid", "pass" if ok else "fail")
    page.screenshot(path=str(OUTDIR / f"{TAG}_06_reset.png"))

    # Second guess after reset to prove the app still works end to end.
    for ch in "slate":
        page.keyboard.press(ch)
        time.sleep(0.2)
    page.keyboard.press("Enter")
    r0 = wait_for(row0_colored, 10)
    record(
        "post-reset guess colored",
        "pass" if r0 else "fail",
        json.dumps([(t["letter"], COLORED.get(t["bg"], t["bg"])) for t in grid(page)[0]]),
    )
    page.screenshot(path=str(OUTDIR / f"{TAG}_07_final.png"))

    browser.close()

BENIGN = [
    re.compile(r"HydrateFallback"),
    re.compile(r"\[vite\]"),
    re.compile(r"React DevTools"),
    re.compile(r"Download the React DevTools"),
    # sandbox proxy blocks fonts.googleapis.com from the browser - env artifact
    re.compile(r"Failed to load resource: net::ERR_CONNECTION_RESET"),
]
bad_responses = [
    b for b in bad_responses if "fonts.googleapis.com" not in b.get("url", "")
]
unexpected = [
    m
    for m in console_msgs
    if m["type"] in ("error", "warning")
    and not any(b.search(m["text"]) for b in BENIGN)
]
record(
    "console: no unexpected errors/warnings",
    "pass" if not unexpected and not page_errors else "anomaly",
    json.dumps(unexpected + page_errors)[:2000],
)
record(
    "network: no 4xx/5xx/failed requests",
    "pass" if not bad_responses else "anomaly",
    json.dumps(bad_responses)[:2000],
)

(OUTDIR / f"{TAG}_results.json").write_text(json.dumps(results, indent=2))
(OUTDIR / f"{TAG}_console.json").write_text(
    json.dumps(
        {"console": console_msgs, "page_errors": page_errors, "bad_responses": bad_responses},
        indent=2,
    )
)
fails = [r for r in results if r["status"] == "fail"]
print(f"\nDONE tag={TAG} fails={len(fails)}")
