"""Independent verification: does reflexle show 'Invalid word.' / 'You already guessed
this word.' toasts, or does received_letter() discard them?

Checks:
 1. control: short guess ('abc' + Enter) -> 'Word must be 5 characters long.' toast
    DOES appear (proves the returned-EventSpec toast mechanism works end-to-end).
 2. invalid 5-letter word ('zzzzz' + Enter) -> row shakes/clears, NO toast.
 3. duplicate valid guess ('crane' twice) -> first accepted (row colored),
    second: NO 'You already guessed this word.' toast, shake/clear instead.

Usage: verify_toast.py <base_url> <shots_dir>
"""

import json
import sys
import time

from playwright.sync_api import sync_playwright

BASE_URL = sys.argv[1]
SHOTS = sys.argv[2]

results = []
console_msgs = []
toast_log = []


def check(name, ok, detail=""):
    results.append({"name": name, "ok": bool(ok), "detail": detail})
    print(("PASS " if ok else "FAIL ") + name + (" | " + detail if detail else ""))


def tile_letters(page):
    """Return the 30 grid tile texts (6 rows x 5)."""
    return page.evaluate(
        """() => {
            // grid tiles are 2em x 2em flex boxes; keyboard buttons are <button>.
            // The guess grid is the first vstack of hstacks of flex divs.
            const all = [...document.querySelectorAll('div.rt-Flex')];
            const tiles = all.filter(d => {
                const s = getComputedStyle(d);
                return s.textTransform === 'uppercase' && d.childElementCount === 1
                    && d.tagName === 'DIV' && s.fontWeight === '700';
            });
            return tiles.slice(0, 30).map(d => d.textContent);
        }"""
    )


def toasts_now(page):
    return page.evaluate(
        """() => [...document.querySelectorAll('[data-sonner-toast]')]
                .map(t => t.textContent.trim())"""
    )


def watch_toasts(page, seconds):
    """Poll for sonner toasts for `seconds`, return all texts seen."""
    seen = []
    deadline = time.time() + seconds
    while time.time() < deadline:
        for t in toasts_now(page):
            if t and t not in seen:
                seen.append(t)
        page.wait_for_timeout(100)
    toast_log.append(seen)
    return seen


def any_shaking(page):
    return page.evaluate(
        """() => [...document.querySelectorAll('div.rt-Flex')].some(d => {
                const s = getComputedStyle(d);
                return s.animationName === 'shake' || s.filter.includes('invert');
            })"""
    )


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = browser.new_page()
    page.on("console", lambda m: console_msgs.append({"type": m.type, "text": m.text}))
    page.on("pageerror", lambda e: console_msgs.append({"type": "pageerror", "text": str(e)}))

    page.goto(BASE_URL, wait_until="load")
    page.wait_for_timeout(3000)  # websocket + hydration

    tiles = tile_letters(page)
    check("grid renders 30 blank tiles", len(tiles) == 30 and all(t.strip() == "" for t in tiles),
          f"got {len(tiles)} tiles")

    # 1. control: short guess -> toast DOES appear
    page.keyboard.type("abc", delay=120)
    page.wait_for_timeout(500)
    check("typed 'abc' echoes", "".join(tile_letters(page)[:3]).lower() == "abc",
          repr(tile_letters(page)[:5]))
    page.keyboard.press("Enter")
    seen = watch_toasts(page, 3)
    page.screenshot(path=f"{SHOTS}/01_short_guess.png")
    check("control: short-guess toast appears",
          any("Word must be 5 characters long." in t for t in seen), f"toasts={seen}")
    for _ in range(3):
        page.keyboard.press("Backspace")
        page.wait_for_timeout(150)
    page.wait_for_timeout(500)
    check("backspace clears row", all(t.strip() == "" for t in tile_letters(page)[:5]),
          repr(tile_letters(page)[:5]))
    # let the control toast expire so it can't pollute later windows
    page.wait_for_timeout(4500)

    # 2. invalid 5-letter word -> NO toast, shake+clear
    page.keyboard.type("zzzzz", delay=120)
    page.wait_for_timeout(400)
    check("typed 'zzzzz' echoes", "".join(tile_letters(page)[:5]).lower() == "zzzzz",
          repr(tile_letters(page)[:5]))
    page.keyboard.press("Enter")
    shake_seen = False
    seen = []
    deadline = time.time() + 3
    shot_done = False
    while time.time() < deadline:
        if not shake_seen and any_shaking(page):
            shake_seen = True
            if not shot_done:
                page.screenshot(path=f"{SHOTS}/02_invalid_shaking.png")
                shot_done = True
        for t in toasts_now(page):
            if t and t not in seen:
                seen.append(t)
        page.wait_for_timeout(50)
    toast_log.append(seen)
    page.screenshot(path=f"{SHOTS}/03_after_invalid.png")
    check("invalid word: row shook", shake_seen)
    check("invalid word: row auto-cleared (bg task)",
          all(t.strip() == "" for t in tile_letters(page)[:5]), repr(tile_letters(page)[:5]))
    check("invalid word: NO toast rendered (claim)", len(seen) == 0, f"toasts={seen}")

    # 3. duplicate valid guess -> NO 'already guessed' toast
    page.keyboard.type("crane", delay=120)
    page.wait_for_timeout(300)
    page.keyboard.press("Enter")
    page.wait_for_timeout(2500)  # accept + tile color transitions
    row1 = tile_letters(page)[:5]
    check("valid guess 'crane' accepted (row kept)",
          "".join(row1).lower() == "crane", repr(row1))
    page.keyboard.type("crane", delay=120)
    page.wait_for_timeout(300)
    page.keyboard.press("Enter")
    seen = []
    shake2 = False
    deadline = time.time() + 3
    while time.time() < deadline:
        if not shake2 and any_shaking(page):
            shake2 = True
        for t in toasts_now(page):
            if t and t not in seen:
                seen.append(t)
        page.wait_for_timeout(50)
    toast_log.append(seen)
    page.screenshot(path=f"{SHOTS}/04_after_duplicate.png")
    check("duplicate guess: row shook", shake2)
    row2 = tile_letters(page)[5:10]
    check("duplicate guess: second row cleared (not accepted)",
          all(t.strip() == "" for t in row2), repr(row2))
    check("duplicate guess: NO toast rendered (claim)", len(seen) == 0, f"toasts={seen}")

    errs = [m for m in console_msgs
            if m["type"] in ("error", "pageerror")
            and "fonts.googleapis.com" not in m["text"]
            and "ERR_CONNECTION_RESET" not in m["text"]]
    check("no unexpected console errors", len(errs) == 0, json.dumps(errs)[:500])

    browser.close()

with open(f"{SHOTS}/results.json", "w") as f:
    json.dump({"results": results, "toast_log": toast_log, "console": console_msgs}, f, indent=2)

print("\nSUMMARY:", sum(r["ok"] for r in results), "/", len(results), "passed")
sys.exit(0 if all(r["ok"] for r in results) else 1)
