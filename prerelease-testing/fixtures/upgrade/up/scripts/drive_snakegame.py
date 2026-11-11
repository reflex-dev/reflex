"""Drive the reflex-examples `snakegame` (singleton bg-task game loop, custom GlobalKeyWatcher component
with add_hooks/add_imports, keyboard control, rx.foreach grid coloured via a state dict lookup).

Usage: drive_snakegame.py <url> <outdir> <tag>
Deterministic run: start heading right from (10,15); queue U x10, L x5 (eats the food at (5,5)), then
D, R, U (self-collision at (6,5)) -> Game Over; RUN resets; Escape toggles via the key watcher; reload.
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
N = 19

BOARD_JS = """() => {
    const probe = (v) => { const d = document.createElement('div'); d.style.backgroundColor = `var(${v})`; document.body.appendChild(d);
                           const c = getComputedStyle(d).backgroundColor; d.remove(); return c; };
    const ref = {snake: probe('--grass-9'), food: probe('--blue-9'), dead: probe('--red-9')};
    const grid = document.querySelector('.rt-Grid');
    if (!grid) return null;
    const cells = [...grid.children].map(c => getComputedStyle(c).backgroundColor);
    const out = {n: cells.length, snake: [], food: [], dead: []};
    cells.forEach((c, i) => { for (const k of ['snake', 'food', 'dead']) if (c === ref[k]) out[k].push(i); });
    return out;
}"""


def board(page):
    return page.evaluate(BOARD_JS)


def stats(page):
    return page.evaluate("""() => { const o = {}; for (const h of document.querySelectorAll('h1,h2,h3,h4,h5,h6')) {
        const t = h.innerText.trim(); if (['RATE', 'SCORE', 'MAGIC'].includes(t)) o[t] = h.nextElementSibling ? h.nextElementSibling.innerText.trim() : null; }
        return o; }""")


def sw(page):
    return page.get_by_role("switch").get_attribute("data-state")


def xy(i):
    return (i % N, i // N)


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
    ctx = browser.new_context(viewport={"width": 1100, "height": 1100}, color_scheme="light")
    page = ctx.new_page()
    run.attach(page, "main")
    page.goto(URL, wait_until="load")
    page.get_by_role("button", name="RUN").wait_for(timeout=60000)
    pump(page, lambda: (board(page) or {}).get("n") == N * N and len(board(page)["food"]) == 0 or True, 5)
    page.wait_for_timeout(1000)
    b0 = board(page)
    st0 = stats(page)
    run.check("initial: 19x19 grid, stats RATE 10 / SCORE 0 / MAGIC 1, switch off", b0 and b0["n"] == 361 and st0 == {"RATE": "10", "SCORE": "0", "MAGIC": "1"} and sw(page) == "unchecked",
              f"n={b0 and b0['n']} stats={st0} switch={sw(page)} snake={b0 and b0['snake']} food={b0 and b0['food']}")
    run.shot(page, "01_initial")
    page.get_by_role("button", name="RUN").click()
    for k in ["ArrowUp"] * 10 + ["ArrowLeft"] * 5 + ["ArrowDown", "ArrowRight", "ArrowUp"]:
        page.keyboard.press(k)
        page.wait_for_timeout(20)
    ok = pump(page, lambda: sw(page) == "checked", 5)
    run.check("RUN starts the loop (switch checked)", ok, sw(page))
    page.wait_for_timeout(2600)
    mid = board(page)
    heads = [xy(i) for i in (mid or {}).get("snake", [])]
    run.notes["mid_snake"] = heads
    run.check("snake moves up the x=10 column (queued ArrowUp via GlobalKeyWatcher)", bool(heads) and all(x == 10 for x, _ in heads) and min(y for _, y in heads) < 13,
              heads)
    ok = pump(page, lambda: stats(page).get("SCORE") == "1", 15)
    st1 = stats(page)
    run.check("eats the food at (5,5): SCORE 1, MAGIC 2, RATE 12", ok and st1 == {"RATE": "12", "SCORE": "1", "MAGIC": "2"}, st1)
    ok = pump(page, lambda: page.get_by_text("Game Over").count() > 0, 15)
    bd = board(page)
    run.check("queued D,R,U -> self-collision -> 'Game Over', dead cell at (6,5), switch off", ok and bd and [xy(i) for i in bd["dead"]] == [(6, 5)] and sw(page) == "unchecked",
              f"dead={[xy(i) for i in (bd or {}).get('dead', [])]} switch={sw(page)} stats={stats(page)}")
    run.shot(page, "02_game_over")
    page.get_by_role("button", name="RUN").click()
    ok = pump(page, lambda: page.get_by_text("Game Over").count() == 0 and stats(page).get("SCORE") == "0", 8)
    run.check("RUN after death resets the game (reset()) and runs", ok and sw(page) == "checked", f"stats={stats(page)} switch={sw(page)}")
    page.wait_for_timeout(1200)
    page.get_by_role("button", name="PAUSE").click()
    pump(page, lambda: sw(page) == "unchecked", 5)
    page.wait_for_timeout(800)
    s1 = board(page)["snake"]
    page.wait_for_timeout(1500)
    s2 = board(page)["snake"]
    run.check("PAUSE freezes the board", s1 == s2 and sw(page) == "unchecked", f"{s1[-2:]} vs {s2[-2:]}")
    page.keyboard.press("Escape")
    ok = pump(page, lambda: sw(page) == "checked", 5)
    page.wait_for_timeout(1200)
    s3 = board(page)["snake"]
    run.check("Escape (key watcher -> flip_switch(~running)) resumes", ok and s3 != s2, f"switch={sw(page)} moved={s3 != s2}")
    page.keyboard.press("Escape")
    ok = pump(page, lambda: sw(page) == "unchecked", 5)
    run.check("Escape again pauses", ok, sw(page))
    page.get_by_role("switch").click()
    ok = pump(page, lambda: sw(page) == "checked", 5)
    page.wait_for_timeout(1000)
    run.check("switch on_change starts the game", ok and board(page)["snake"] != s3, sw(page))
    # on-screen arrow buttons
    page.locator("button.rt-IconButton").filter(has=page.locator("svg.lucide-arrow-down")).first.click() if page.locator("svg.lucide-arrow-down").count() else None
    page.wait_for_timeout(1300)
    run.notes["after_arrow_button"] = [xy(i) for i in board(page)["snake"]]
    # reload while running: bg loop keeps going server-side, page re-hydrates the live game
    page.reload(wait_until="load")
    page.get_by_role("button", name="RUN").wait_for(timeout=30000)
    pump(page, lambda: (board(page) or {}).get("n") == 361, 10)
    r1 = board(page)["snake"]
    page.wait_for_timeout(1500)
    r2 = board(page)["snake"]
    run.check("reload while running: live board keeps moving, switch reflects running", r1 != r2 and sw(page) == "checked", f"switch={sw(page)} moved={r1 != r2}")
    page.get_by_role("button", name="PAUSE").click()
    pump(page, lambda: sw(page) == "unchecked", 5)
    run.shot(page, "03_after_reload")
    browser.close()
sys.exit(run.finish())
