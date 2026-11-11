"""Drive reflex-examples overkey (typing game: ClientStateVar user_input, background `tick`, rx.memo, radix selects).

Usage: drive_overkey.py <url> <outdir> <tag> [profile_dir (unused)]
Flows: words render after hydration; time limit select -> "5 seconds"; typing updates the client-side
ClientStateVar (letters turn opaque / pink when wrong) with no websocket event per keystroke (only start_timer);
background tick counts 5 -> 0; "Time's up!" memo -> receive_user_input -> "N WPM, X% accuracy"; Restart
(rotate-ccw) brings the selects back and (witness memo) should clear the typed input (examples#324 / TP-04:
it does not); language select changes words; reload mid-game: timer resets (on_load), ClientStateVar
value after reload is recorded; second game after reload works.
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "up" / "scripts"))
from harness import CHROMIUM, Run, guard_driver_python, wait_for  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

guard_driver_python()
URL, OUT, TAG = sys.argv[1:4]
run = Run(TAG, OUT)

LETTERS_JS = """() => [...document.querySelectorAll('#words .letter')].map(d => {
  const s = getComputedStyle(d);
  return [d.textContent, s.opacity, s.backgroundColor]; })"""


def letters(page):
    return page.evaluate(LETTERS_JS)


def paragraph(page):
    return "".join(t for t, _, _ in letters(page))


def in_bounds(page):
    return sum(1 for _, o, _ in letters(page) if o == "1")


def wrong(page):
    return sum(1 for _, _, bg in letters(page) if bg == "rgb(255, 192, 203)")


def input_value(page):
    return page.locator("input").first.evaluate("e => e.value")


def status_text(page):
    # the flex next to the restart icon button: current_time or the result line
    loc = page.locator("button:has(svg.lucide-rotate-ccw) + div")
    return loc.first.inner_text().strip() if loc.count() else None


def sent_events():
    return [f for f in run.ws if f["dir"] == "out" and '"name"' in f.get("payload", "")]


def event_names(frames):
    names = []
    for f in frames:
        p = f["payload"]
        i = p.find('"name":"')
        if i >= 0:
            names.append(p[i + 8:p.find('"', i + 8)].rsplit(".", 1)[-1])
    return names


def pick(page, index, option):
    page.get_by_role("combobox").nth(index).click()
    page.get_by_role("option", name=option, exact=True).click()
    time.sleep(0.6)


def play(page, label, n_chars, wrong_at=None, limit="5 seconds"):
    """Type n_chars of the paragraph (one wrong char at index wrong_at) and wait for the result."""
    para = paragraph(page)
    text = para[:n_chars]
    if wrong_at is not None:
        text = text[:wrong_at] + ("x" if text[wrong_at] != "x" else "y") + text[wrong_at + 1:]
    page.locator("input").first.focus()
    before = len(sent_events())
    page.keyboard.type(text, delay=25)
    time.sleep(0.4)
    ev = event_names(sent_events()[before:])
    run.check(f"{label}: typed {len(text)} chars -> input value matches", input_value(page) == text,
              f"{input_value(page)!r} vs {text!r}")
    ib = in_bounds(page)
    run.check(f"{label}: letters in bounds == typed length (ClientStateVar drives render)", ib == len(text), ib)
    if wrong_at is not None:
        run.check(f"{label}: wrong letter highlighted pink", wrong(page) == 1, wrong(page))
    run.check(f"{label}: no websocket event per keystroke (client-side state)",
              ev.count("start_timer") == 1 and len([e for e in ev if e not in ("start_timer", "tick")]) == 0,
              ev)
    return text


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM)
    ctx = browser.new_context(viewport={"width": 1200, "height": 900})
    page = ctx.new_page()
    run.attach(page)
    page.goto(URL, wait_until="load")
    ok = wait_for(lambda: len(letters(page)) > 50, 60)
    run.check("load: words rendered after hydration", bool(ok), len(letters(page)))
    run.check("load: two selects (language, time)", page.get_by_role("combobox").count() == 2,
              page.get_by_role("combobox").count())
    first_para = paragraph(page)
    run.notes["initial_letters"] = len(letters(page))
    run.shot(page, "01_loaded")

    pick(page, 1, "5 seconds")
    ok = wait_for(lambda: "5 seconds" in page.get_by_role("combobox").nth(1).inner_text(), 5)
    run.check("time select -> 5 seconds", bool(ok), page.get_by_role("combobox").nth(1).inner_text())
    ok = wait_for(lambda: 0 < len(letters(page)) < len(first_para), 10)
    run.check("time select regenerates fewer words (25 words)", bool(ok), len(letters(page)))

    t0 = time.time()
    typed = play(page, "game1", 12, wrong_at=3)
    seen = []
    deadline = time.time() + 15
    while time.time() < deadline:
        s = status_text(page)
        if s and (not seen or seen[-1] != s):
            seen.append(s)
        if s and "WPM" in s:
            break
        time.sleep(0.15)
    run.notes["game1_status_seq"] = seen
    run.notes["game1_seconds_to_result"] = round(time.time() - t0, 2)
    nums = [int(x) for x in seen if x.isdigit()]
    run.check("game1: background tick counts down (sees >=3 distinct values, decreasing)",
              len(nums) >= 3 and nums == sorted(nums, reverse=True), seen)
    run.check("game1: result line shows WPM + accuracy", bool(seen) and "WPM" in seen[-1], seen[-1:] if seen else seen)
    # 11 correct letters of 12 over 5 seconds: wpm = 11/5*60/5 = 26.4, accuracy 91.67%
    run.check("game1: WPM/accuracy values", bool(seen) and seen[-1].startswith("26.4 WPM") and "91.67%" in seen[-1],
              seen[-1:] if seen else seen)
    run.check("game1: Time's up! overlay", page.get_by_text("Time's up!").count() == 1)
    ev = event_names(sent_events())
    run.notes["game1_events"] = ev
    # informational: a background task's returned EventHandler is chained server-side on 0.10.1 (no client frames)
    run.notes["game1_client_sent_tick_frames"] = ev.count("tick")
    run.shot(page, "02_result")

    page.locator("button:has(svg.lucide-rotate-ccw)").first.click()
    ok = wait_for(lambda: page.get_by_role("combobox").count() == 2, 8)
    run.check("restart: selects come back", bool(ok))
    time.sleep(1)
    iv = input_value(page)
    run.notes["after_restart_input"] = iv
    # examples#324 (TP-04): witness memo should clear it; it has not on earlier versions
    run.check("restart: typed ClientStateVar input cleared (examples#324)", "pass" if iv == "" else "anomaly", repr(iv))
    run.notes["after_restart_in_bounds"] = in_bounds(page)
    run.shot(page, "03_restart")

    pick(page, 0, "Deutsch")
    ok = wait_for(lambda: "Deutsch" in page.get_by_role("combobox").nth(0).inner_text(), 5)
    run.check("language select -> Deutsch", bool(ok), page.get_by_role("combobox").nth(0).inner_text())
    para_de = paragraph(page)
    run.check("language change regenerates words", para_de != first_para and len(para_de) > 0, para_de[:40])

    # reload mid-game
    pick(page, 1, "15 seconds")
    page.locator("input").first.focus()
    page.keyboard.press("Backspace")  # existing value from #324 -> clear it
    for _ in range(len(input_value(page))):
        page.keyboard.press("Backspace")
    time.sleep(0.3)
    para = paragraph(page)
    page.keyboard.type(para[:6], delay=25)
    ok = wait_for(lambda: (status_text(page) or "").isdigit(), 5)
    run.check("game2 (15s): timer started", bool(ok), status_text(page))
    time.sleep(1.5)
    mid = status_text(page)
    run.notes["game2_before_reload"] = {"status": mid, "input": input_value(page), "in_bounds": in_bounds(page)}
    page.reload(wait_until="load")
    ok = wait_for(lambda: len(letters(page)) > 20, 30)
    time.sleep(2.5)
    after = {"status": status_text(page), "input": input_value(page), "in_bounds": in_bounds(page),
             "selects": page.get_by_role("combobox").count(),
             "time_select": page.get_by_role("combobox").nth(1).inner_text() if page.get_by_role("combobox").count() > 1 else None,
             "language": page.get_by_role("combobox").nth(0).inner_text() if page.get_by_role("combobox").count() else None,
             "same_words": paragraph(page) == para}
    run.notes["game2_after_reload"] = after
    run.check("reload mid-game: timer reset by on_load (selects shown, no countdown)",
              after["selects"] == 2 and after["status"] is None, after)
    run.check("reload mid-game: ClientStateVar input reset to default ''", after["input"] == "", after)
    run.shot(page, "04_after_reload")
    # a background tick from the pre-reload game may still be running for the same token
    time.sleep(3)
    run.notes["game2_after_reload_3s"] = {"status": status_text(page), "selects": page.get_by_role("combobox").count()}
    run.check("reload mid-game: stale background tick does not restart the countdown",
              page.get_by_role("combobox").count() == 2, run.notes["game2_after_reload_3s"])

    # game 3 after reload, 5 seconds, all correct
    pick(page, 1, "5 seconds")
    time.sleep(0.5)
    play(page, "game3", 10)
    ok = wait_for(lambda: "WPM" in (status_text(page) or ""), 12)
    run.check("game3: result after reload", bool(ok) and (status_text(page) or "").startswith("24 WPM"), status_text(page))
    run.check("game3: 100% accuracy", "100.00%" in (status_text(page) or ""), status_text(page))
    run.shot(page, "05_game3")
    ctx.close()
    browser.close()
print(json.dumps(run.notes, default=str)[:2500])
sys.exit(run.finish())
