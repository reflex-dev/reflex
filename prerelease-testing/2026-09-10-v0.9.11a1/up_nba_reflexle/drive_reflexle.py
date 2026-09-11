"""Drive the reflex-examples `reflexle` app (Wordle clone) end to end in Chromium with REAL
key presses, exercising the third-party `reflex-global-hotkey` component.

usage: drive_reflexle.py <frontend_url> <artifacts_dir> <label> [<app_dir>]

Exercises: document-level keydown via reflex_global_hotkey.global_hotkey_watcher (add_hooks +
useEffect + an EventChain built from rx.Var.create([...]).contains(key)), @rx.memo character
boxes/keyboard buttons with Var args, rx.foreach over a computed list-of-tuples var,
rx.match/rx.cond styling, rx.toast (sonner) for the three error paths, a background event
(set_is_wrong_guess_false) that clears the shake, rx.set_focus, color mode + high contrast,
the LOST end state, session persistence across reload, and the on_load handler.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from drive_common import Run, wait_for  # noqa: E402

URL, ART, LABEL = sys.argv[1], sys.argv[2], sys.argv[3]
APP_DIR = sys.argv[4] if len(sys.argv) > 4 else None

# 5-letter words that are in valid_guess but NOT in possible_solution, so six of them
# can never win the game -> a deterministic LOST end state.
LOSING_GUESSES = ["homes", "gawks", "bumph", "vexed", "quips", "mylar"]
INVALID_WORD = "zzzzz"

GRID_JS = """
() => {
  const boxes = [...document.querySelectorAll('div.rt-Flex')].filter(d => {
    const r = d.getBoundingClientRect();
    return Math.abs(r.width - r.height) < 2 && r.width > 30 && r.width < 90 && d.children.length <= 1;
  });
  boxes.sort((a, b) => {
    const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
    return (ra.y - rb.y) || (ra.x - rb.x);
  });
  const cells = boxes.map(d => ({
    t: d.innerText.trim(),
    bg: getComputedStyle(d).backgroundColor,
    border: getComputedStyle(d).borderTopWidth + ' ' + getComputedStyle(d).borderTopColor,
  }));
  const rows = [];
  for (let i = 0; i < cells.length; i += 5) rows.push(cells.slice(i, i + 5));
  return rows;
}
"""

KEYBOARD_JS = """
() => [...document.querySelectorAll('button')]
        .filter(b => b.innerText.trim().length > 0)
        .map(b => ({t: b.innerText.trim(), bg: getComputedStyle(b).backgroundColor}))
"""


def grid(page):
    return page.evaluate(GRID_JS)


def row_text(page, i):
    g = grid(page)
    return "".join(c["t"] for c in g[i]) if i < len(g) else None


def keyboard(page):
    return page.evaluate(KEYBOARD_JS)


def type_word(page, word, delay=110):
    for ch in word:
        page.keyboard.press(ch)
        page.wait_for_timeout(delay)


def toasts(page):
    return page.evaluate(
        "() => [...document.querySelectorAll('[data-sonner-toast], li[data-sonner-toast], ol[data-sonner-toaster] li')]"
        ".map(t => t.innerText.replace(/\\s+/g,' ').trim())"
    )


with Run(ART, LABEL) as run:
    ctx, page = run.new_page("reflexle")
    page.set_viewport_size({"width": 1280, "height": 1000})
    page.goto(URL, wait_until="load", timeout=90_000)
    page.wait_for_timeout(3000)

    # 1. page + grid + on-screen keyboard render
    ok = wait_for(lambda: len(grid(page)) == 6 and len(grid(page)[0]) == 5, 30)
    g = grid(page)
    kb = keyboard(page)
    run.record(
        "reflexle_page_loads",
        "pass" if ok and len(kb) == 28 else "fail",
        f"title={page.title()!r} grid_rows={len(g)} cols={len(g[0]) if g else 0} keyboard_buttons={len(kb)} "
        f"(28 expected: 26 letters + backspace + enter)",
    )
    run.shot(page, "01_index.png", full_page=True)

    # 2. real key presses reach the backend through global_hotkey_watcher
    type_word(page, "homes")
    ok = wait_for(lambda: row_text(page, 0) == "HOMES", 10)
    run.record(
        "global_hotkey_letters",
        "pass" if ok else "fail",
        f"typed 'homes' with real key presses -> row0={row_text(page, 0)!r}",
    )
    run.shot(page, "02_typed_homes.png")

    # 3. Backspace
    page.keyboard.press("Backspace")
    ok = wait_for(lambda: row_text(page, 0) == "HOME", 8)
    run.record("global_hotkey_backspace", "pass" if ok else "fail", f"row0={row_text(page, 0)!r} (expect HOME)")

    # 4. Ctrl+Backspace: the app has a "Ctrl+Backspace" branch but reflex's key_event only
    #    forwards event.key, so it arrives as plain "Backspace" -> deletes ONE letter.
    page.keyboard.press("Control+Backspace")
    page.wait_for_timeout(900)
    after_ctrl = row_text(page, 0)
    run.record(
        "ctrl_backspace_deletes_one_letter",
        "anomaly" if after_ctrl == "HOM" else ("pass" if after_ctrl == "" else "fail"),
        f"row0={after_ctrl!r}; app expects a 'Ctrl+Backspace' key string (clear row) but reflex "
        "key_event forwards only event.key, so Ctrl+Backspace == Backspace (app-level dead branch)",
    )

    # 5. Enter with a short word -> length toast (clear the row first)
    for _ in range(6):
        page.keyboard.press("Backspace")
        page.wait_for_timeout(90)
    wait_for(lambda: row_text(page, 0) == "", 6)
    type_word(page, "ab")
    page.keyboard.press("Enter")
    ok = wait_for(lambda: any("5 characters" in t for t in toasts(page)), 8)
    run.record(
        "toast_word_too_short",
        "pass" if ok else "fail",
        f"toasts={toasts(page)} (expect 'Word must be 5 characters long.')",
    )
    run.shot(page, "03_toast_short.png")
    for _ in range(6):
        page.keyboard.press("Backspace")
        page.wait_for_timeout(80)
    page.wait_for_timeout(800)

    # 6. Enter with an invalid word -> toast + shake + background clear
    type_word(page, INVALID_WORD)
    page.keyboard.press("Enter")
    ok_toast = wait_for(lambda: any("Invalid word" in t for t in toasts(page)), 8)
    run.shot(page, "04_toast_invalid.png")
    ok_cleared = wait_for(lambda: row_text(page, 0) == "", 8)
    run.record(
        "invalid_word_shake_and_background_clear",
        "pass" if ok_cleared else "fail",
        f"row cleared 0.3 s later by the background set_is_wrong_guess_false event={ok_cleared} "
        f"row0={row_text(page, 0)!r}",
    )
    run.record(
        "invalid_word_toast_dropped_by_app",
        "pass" if not ok_toast else "anomaly",
        "no toast for an invalid word: ReflexleGame.guess() builds rx.toast('Invalid word.') but "
        "Reflexle.received_letter discards its return value and returns set_is_wrong_guess_false "
        f"instead (upstream example bug, both reflex versions). toasts={toasts(page)}",
    )

    # 7. a valid guess colours the row and the on-screen keyboard
    type_word(page, LOSING_GUESSES[0])
    page.keyboard.press("Enter")
    ok = wait_for(lambda: row_text(page, 0) == LOSING_GUESSES[0].upper() and all(
        c["bg"] != "rgba(0, 0, 0, 0)" for c in grid(page)[0]
    ), 12)
    g1 = grid(page)
    kb1 = keyboard(page)
    coloured_kb = [k for k in kb1 if k["bg"] not in {kb[0]["bg"]}]
    run.record(
        "valid_guess_colours_row_and_keyboard",
        "pass" if ok else "fail",
        f"row0={[ (c['t'], c['bg']) for c in g1[0] ]}; keyboard keys whose colour changed="
        f"{[k['t'] for k in coloured_kb]}",
    )
    run.shot(page, "05_first_guess.png", full_page=True)

    # 8. duplicate guess toast
    type_word(page, LOSING_GUESSES[0])
    page.keyboard.press("Enter")
    ok_dup_toast = wait_for(lambda: any("already guessed" in t for t in toasts(page)), 6)
    ok_dup_clear = wait_for(lambda: row_text(page, 1) == "", 8)
    run.record(
        "duplicate_guess_rejected",
        "pass" if ok_dup_clear and not ok_dup_toast else "fail",
        f"row1 cleared={ok_dup_clear}; toast shown={ok_dup_toast} (same discarded-EventSpec app bug "
        f"as the invalid-word path). toasts={toasts(page)}",
    )

    # 9. on-screen keyboard buttons (memo'd component, event arg bound per button)
    for letter in "gaw":
        page.locator(f"button:text-is('{letter}')").first.click()
        page.wait_for_timeout(400)
    ok = wait_for(lambda: row_text(page, 1) == "GAW", 8)
    run.record(
        "onscreen_keyboard_clicks",
        "pass" if ok else "fail",
        f"clicked G,A,W -> row1={row_text(page, 1)!r}",
    )
    # finish that guess with the ⌫ / ↵ buttons
    page.locator("button:text-is('⌫')").first.click()
    page.wait_for_timeout(500)
    after_bs_button = row_text(page, 1)
    for letter in "wks":
        page.locator(f"button:text-is('{letter}')").first.click()
        page.wait_for_timeout(350)
    page.locator("button:text-is('↵')").first.click()
    ok = wait_for(lambda: row_text(page, 1) == "GAWKS", 10)
    run.record(
        "onscreen_backspace_and_enter_buttons",
        "pass" if ok and after_bs_button == "GA" else "fail",
        f"after ⌫ row1={after_bs_button!r}; after typing WKS + ↵ row1={row_text(page, 1)!r}",
    )
    run.shot(page, "06_two_guesses.png", full_page=True)

    # 10. high contrast toggle recolours the already-revealed cells
    before_bgs = [c["bg"] for row in grid(page)[:2] for c in row]
    page.locator("button.rt-IconButton, button.rt-BaseButton").nth(1).click()
    page.wait_for_timeout(1500)
    after_bgs = [c["bg"] for row in grid(page)[:2] for c in row]
    run.record(
        "high_contrast_toggle",
        "pass" if before_bgs != after_bgs else "fail",
        f"cell backgrounds changed: {sorted(set(before_bgs))} -> {sorted(set(after_bgs))}",
    )
    run.shot(page, "07_high_contrast.png", full_page=True)
    page.locator("button.rt-IconButton, button.rt-BaseButton").nth(1).click()
    page.wait_for_timeout(1200)

    # 11. color mode toggle
    before_cls = page.evaluate("() => document.documentElement.className")
    page.locator("button.rt-IconButton, button.rt-BaseButton").nth(2).click()
    page.wait_for_timeout(1500)
    after_cls = page.evaluate("() => document.documentElement.className")
    run.record(
        "color_mode_toggle",
        "pass" if before_cls != after_cls else "fail",
        f"documentElement.class {before_cls!r} -> {after_cls!r}",
    )
    run.shot(page, "08_dark.png", full_page=True)

    # 12. reload keeps the session's two guesses (disk state manager)
    page.reload(wait_until="load")
    page.wait_for_timeout(3500)
    r0, r1 = row_text(page, 0), row_text(page, 1)
    run.record(
        "state_survives_reload",
        "pass" if r0 == "HOMES" and r1 == "GAWKS" else "fail",
        f"after reload row0={r0!r} row1={r1!r} (on_load must not reset a game in progress)",
    )
    run.shot(page, "09_after_reload.png", full_page=True)

    # 13. play out the remaining four guesses -> deterministic LOST
    for word in LOSING_GUESSES[2:]:
        type_word(page, word, delay=90)
        page.keyboard.press("Enter")
        page.wait_for_timeout(1200)
    # NB: the banner text is CSS text-transform:uppercase, and inner_text() returns the
    # transformed text ("WORD IS MARSH"), so match case-insensitively.
    ok = wait_for(lambda: "word is" in page.inner_text("body").lower(), 15)
    body = page.inner_text("body")
    revealed = next((ln for ln in body.splitlines() if "word is" in ln.lower()), None)
    run.record(
        "lost_game_reveals_word",
        "pass" if ok else "fail",
        f"after 6 non-solution guesses: banner={revealed!r}; rows="
        f"{[''.join(c['t'] for c in row) for row in grid(page)]}",
    )
    run.shot(page, "10_lost.png", full_page=True)

    # 14. further keys are ignored once the game is over
    type_word(page, "ab")
    page.wait_for_timeout(800)
    rows_after = ["".join(c["t"] for c in row) for row in grid(page)]
    run.record(
        "keys_ignored_after_game_over",
        "pass" if all(len(r) == 5 for r in rows_after) else "fail",
        f"rows={rows_after}",
    )

    # 15. play again resets and focuses the hidden #guesses button (rx.set_focus)
    page.locator("button.rt-IconButton, button.rt-BaseButton").nth(0).click()
    ok = wait_for(lambda: all(c["t"] == "" for row in grid(page) for c in row), 10)
    focused = page.evaluate("() => document.activeElement && document.activeElement.id")
    run.record(
        "play_again_resets_and_sets_focus",
        "pass" if ok and focused == "guesses" else ("anomaly" if ok else "fail"),
        f"grid cleared={ok}; document.activeElement.id={focused!r} (rx.set_focus('guesses'))",
    )
    run.shot(page, "11_after_play_again.png", full_page=True)

    # 16. keys still work after the reset (the useEffect listener survives the re-render)
    type_word(page, "vex")
    ok = wait_for(lambda: row_text(page, 0) == "VEX", 8)
    run.record(
        "hotkeys_work_after_reset",
        "pass" if ok else "fail",
        f"row0={row_text(page, 0)!r} after reset + 3 key presses",
    )

    # 17. a second tab gets its own game (separate state token), keys go to the focused tab only
    ctx2, page2 = run.new_page("tab2")
    page2.goto(URL, wait_until="load", timeout=90_000)
    page2.wait_for_timeout(3000)
    tab2_row0 = row_text(page2, 0)
    type_word(page2, "quip")
    page2.wait_for_timeout(600)
    run.record(
        "second_tab_independent_game",
        "pass" if tab2_row0 == "" and row_text(page2, 0) == "QUIP" else "fail",
        f"new context row0 before={tab2_row0!r} after typing 'quip'={row_text(page2, 0)!r}; "
        f"first tab row0 still {row_text(page, 0)!r}",
    )
    ctx2.close()

    # 18. installed frontend packages
    if APP_DIR:
        pkg = Path(APP_DIR) / ".web" / "package.json"
        if pkg.exists():
            data = json.loads(pkg.read_text())
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            (Path(ART) / "npm_versions.json").write_text(json.dumps(deps, indent=2, sort_keys=True))
            run.record("npm_versions_recorded", "pass", json.dumps(deps, sort_keys=True))

    unexpected = run.unexpected_console()
    # fonts.googleapis.com / fonts.gstatic.com are unreachable from the browser in this
    # container (no proxy configured for Chromium); those failures are environmental.
    env_noise = [b for b in run.bad if "fonts.g" in str(b.get("url", ""))]
    real_bad = [b for b in run.bad if "fonts.g" not in str(b.get("url", ""))]
    run.record(
        "browser_console_clean",
        "pass" if not unexpected else "anomaly",
        f"{len(unexpected)} unexpected: {json.dumps(unexpected[:8], ensure_ascii=False)}",
    )
    run.record(
        "no_bad_http_responses",
        "pass" if not real_bad else "anomaly",
        f"{len(real_bad)} non-environmental failures: {json.dumps(real_bad[:8])}; "
        f"{len(env_noise)} blocked Google-Fonts requests (environmental)",
    )
    run.record(
        "no_page_errors",
        "pass" if not run.page_errors else "fail",
        f"{len(run.page_errors)}: {json.dumps(run.page_errors[:5])}",
    )
    ctx.close()
