"""Playwright driver for the snakegame example app.

Usage: python drive_snakegame.py <frontend_url> <outdir> <tag>

Real arrow-key gameplay: starts the game, measures background-task tick
throughput, pauses/resumes with Escape, steers the snake onto the food by
polling the head position (score/magic/rate must update), forces a
self-collision with queued relative turns (Game Over), and restarts.
Writes screenshots + <tag>_results.json + <tag>_console.json to outdir.
"""

import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

URL, OUTDIR, TAG = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
OUTDIR.mkdir(parents=True, exist_ok=True)
N = 19

results = []
console_msgs = []
page_errors = []
bad_responses = []

BOARD_JS = """
() => {
  let grid = null;
  for (const d of document.querySelectorAll('div')) {
    if (d.children.length === 361) { grid = d; break; }
  }
  if (!grid) return null;
  const vars = ['--gray-5','--grass-9','--blue-9','--red-9'];
  const probe = document.createElement('div');
  document.body.appendChild(probe);
  const colors = {};
  for (const v of vars) {
    probe.style.backgroundColor = `var(${v})`;
    colors[getComputedStyle(probe).backgroundColor] = v;
  }
  probe.remove();
  const out = {snake: [], food: [], dead: [], other: []};
  Array.from(grid.children).forEach((c, i) => {
    const bg = getComputedStyle(c).backgroundColor;
    const v = colors[bg];
    if (v === '--grass-9') out.snake.push(i);
    else if (v === '--blue-9') out.food.push(i);
    else if (v === '--red-9') out.dead.push(i);
    else if (v !== '--gray-5') out.other.push([i, bg]);
  });
  return out;
}
"""

STATS_JS = """
() => {
  const get = (label) => {
    for (const h of document.querySelectorAll('.rt-Heading')) {
      if (h.textContent === label) {
        const sib = h.parentElement.querySelectorAll('.rt-Heading');
        if (sib.length >= 2) return sib[1].textContent;
      }
    }
    return null;
  };
  return {rate: get('RATE'), score: get('SCORE'), magic: get('MAGIC')};
}
"""


def record(step, status, detail=""):
    results.append({"step": step, "status": status, "detail": detail})
    print(f"[{status.upper():7}] {step}: {detail}", flush=True)


def wait_for(fn, timeout=10.0, interval=0.1):
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


def xy(i):
    return (i % N, i // N)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = browser.new_page(viewport={"width": 900, "height": 1000})
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

    def board():
        return page.evaluate(BOARD_JS)

    def stats():
        return page.evaluate(STATS_JS)

    def switch_on():
        return page.get_attribute("button[role=switch]", "aria-checked") == "true"

    page.goto(URL, wait_until="load", timeout=60000)
    b = wait_for(board, 30)
    record("load: 19x19 grid renders (361 cells)", "pass" if b else "fail")
    s = wait_for(
        lambda: (lambda v: v if v["rate"] == "10" else None)(stats()), 15
    )
    record(
        "load: initial stats RATE=10 SCORE=0 MAGIC=1",
        "pass" if s and s == {"rate": "10", "score": "0", "magic": "1"} else "fail",
        json.dumps(s or stats()),
    )
    page.screenshot(path=str(OUTDIR / f"{TAG}_01_initial.png"))

    # Start the game; wait until websocket round-trips (switch flips + snake appears).
    def started():
        page.click("button:has-text('RUN')")
        time.sleep(0.5)
        return switch_on()

    ok = wait_for(started, 20, 0.2)
    record("RUN starts game (switch reflects running)", "pass" if ok else "fail")
    ok = wait_for(lambda: board()["snake"], 10)
    record("game loop draws snake cells", "pass" if ok else "fail",
           f"snake={ok}")

    # Throughput: board must change on ~every 0.5s tick.
    changes = 0
    prev = tuple(board()["snake"])
    t_end = time.time() + 4.0
    while time.time() < t_end:
        time.sleep(0.08)
        cur = tuple(board()["snake"])
        if cur != prev:
            changes += 1
            prev = cur
    record(
        "tick throughput: >=6 board updates in 4s",
        "pass" if changes >= 6 else "fail",
        f"observed {changes} updates (expect ~8)",
    )
    page.screenshot(path=str(OUTDIR / f"{TAG}_02_running.png"))

    # Escape pauses and resumes (key event with expression arg).
    page.keyboard.press("Escape")
    ok = wait_for(lambda: not switch_on(), 5)
    time.sleep(0.8)  # let the in-flight tick land (loop checks running pre-sleep)
    snap = tuple(board()["snake"])
    time.sleep(1.2)
    frozen = tuple(board()["snake"]) == snap
    record("Escape pauses game", "pass" if ok and frozen else "fail",
           f"switch_off={bool(ok)} board_frozen={frozen}")
    page.keyboard.press("Escape")
    ok = wait_for(lambda: switch_on(), 5)
    moved = wait_for(lambda: tuple(board()["snake"]) != snap, 5)
    record("Escape resumes game", "pass" if ok and moved else "fail")

    # Steer the snake onto the food with real arrow keys.
    def head_tracker():
        state = {"prev": set(board()["snake"]), "head": None}

        def poll():
            cur = set(board()["snake"])
            added = cur - state["prev"]
            if len(added) == 1:
                state["head"] = xy(next(iter(added)))
            state["prev"] = cur
            return state["head"]

        return poll

    poll_head = head_tracker()
    food = wait_for(lambda: board()["food"], 5)
    food_xy = xy(food[0]) if food else None
    record("food rendered", "pass" if food else "fail", f"food={food_xy}")

    page.keyboard.press("ArrowUp")
    target_y = food_xy[1] if food_xy else 5
    ok = wait_for(lambda: (h := poll_head()) and h[1] == target_y, 25, 0.05)
    record(
        "ArrowUp steers snake to food row",
        "pass" if ok else "fail",
        f"head={ok}",
    )
    page.keyboard.press("ArrowLeft")
    got_food = wait_for(lambda: stats()["score"] == "1", 25, 0.1)
    record(
        "ArrowLeft onto food: SCORE increments",
        "pass" if got_food else "fail",
        json.dumps(stats()),
    )
    s = stats()
    record(
        "eating food bumps MAGIC=2 RATE=12",
        "pass" if s == {"rate": "12", "score": "1", "magic": "2"} else "fail",
        json.dumps(s),
    )
    page.screenshot(path=str(OUTDIR / f"{TAG}_03_after_food.png"))

    # Queue four relative-right turns -> snake loops into itself -> Game Over.
    for _ in range(4):
        page.keyboard.press(".")
        time.sleep(0.05)
    over = wait_for(
        lambda: page.locator("text=Game Over").count() > 0, 15, 0.2
    )
    dead_cell = board()["dead"]
    record(
        "queued rel-right turns cause self-collision: Game Over",
        "pass" if over else "fail",
        f"dead_cells={dead_cell}",
    )
    record("dead cell rendered red", "pass" if dead_cell else "fail")
    ok = wait_for(lambda: not switch_on(), 5)
    record("game stops on death (switch off)", "pass" if ok else "fail")
    page.screenshot(path=str(OUTDIR / f"{TAG}_04_game_over.png"))

    # RUN after death resets the game.
    page.click("button:has-text('RUN')")
    ok = wait_for(lambda: stats()["score"] == "0" and switch_on(), 10)
    record("RUN after death resets score and restarts", "pass" if ok else "fail",
           json.dumps(stats()))
    moved = wait_for(lambda: board()["snake"], 10)
    record("snake moving again after restart", "pass" if moved else "fail")

    # Pause via the switch itself (on_change handler).
    page.click("button[role=switch]")
    ok = wait_for(lambda: not switch_on(), 5)
    time.sleep(0.8)
    snap = tuple(board()["snake"])
    time.sleep(1.2)
    frozen = tuple(board()["snake"]) == snap
    record("switch click pauses game", "pass" if ok and frozen else "fail",
           f"switch_off={bool(ok)} board_frozen={frozen}")
    page.screenshot(path=str(OUTDIR / f"{TAG}_05_final.png"))

    browser.close()

BENIGN = [
    re.compile(r"HydrateFallback"),
    re.compile(r"\[vite\]"),
    re.compile(r"React DevTools"),
    re.compile(r"Download the React DevTools"),
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
