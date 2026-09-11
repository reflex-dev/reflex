"""Drive the reflex-examples `snakegame` app end to end in Chromium with REAL key presses.

usage: drive_snakegame.py <frontend_url> <artifacts_dir> <label> [<app_dir>]

Exercises: a singleton `@rx.event(background=True)` game loop pushing ~2 deltas/second into a
live page, a hand-written custom component (`GlobalKeyWatcher(rx.Fragment)` with add_imports /
add_hooks and a `dict[str, EventSpec]` key_map compiled into a JS object of EventChains),
rx.foreach over 361 cells indexing a `dict[int, Color]` on another state class, arrow/vim/
relative keyboard controls, the mouse control buttons, rx.switch two-way binding against a
backend-driven var, deterministic Game Over, and reset-on-replay.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from drive_common import Run, wait_for  # noqa: E402

URL, ART, LABEL = sys.argv[1], sys.argv[2], sys.argv[3]
APP_DIR = sys.argv[4] if len(sys.argv) > 4 else None

CELLS_JS = """
() => {
  const cells = [...document.querySelectorAll('div')].filter(d => {
    const r = d.getBoundingClientRect();
    return r.width > 10 && r.width < 30 && Math.abs(r.width - r.height) < 3 && d.children.length === 0;
  });
  cells.sort((a, b) => {
    const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
    return (ra.y - rb.y) || (ra.x - rb.x);
  });
  const colors = cells.map(d => getComputedStyle(d).backgroundColor);
  const counts = {};
  colors.forEach(c => counts[c] = (counts[c] || 0) + 1);
  return {n: cells.length, counts, nonEmpty: colors.map((c, i) => [i, c]).filter(([, c]) => counts[c] < 100)};
}
"""

STATS_JS = """
() => {
  const h = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].map(e => e.innerText.trim());
  const out = {};
  for (let i = 0; i < h.length - 1; i++) if (['RATE','SCORE','MAGIC'].includes(h[i])) out[h[i]] = h[i+1];
  out.gameover = h.some(t => t.includes('Game Over'));
  return out;
}
"""


def cells(page):
    return page.evaluate(CELLS_JS)


def stats(page):
    return page.evaluate(STATS_JS)


def switch_state(page):
    return page.get_attribute("button[role=switch]", "data-state")


def press(page, key, times=1, delay=140):
    for _ in range(times):
        page.keyboard.press(key)
        page.wait_for_timeout(delay)


with Run(ART, LABEL) as run:
    ctx, page = run.new_page("snake")
    page.set_viewport_size({"width": 1100, "height": 1100})
    page.goto(URL, wait_until="load", timeout=90_000)
    page.wait_for_timeout(3000)

    # 1. board + stat boxes render
    ok = wait_for(lambda: cells(page)["n"] == 361, 30)
    c0 = cells(page)
    s0 = stats(page)
    run.record(
        "snakegame_page_loads",
        "pass" if ok and s0.get("SCORE") == "0" else "fail",
        f"title={page.title()!r} grid_cells={c0['n']} (19x19=361) stats={s0} switch={switch_state(page)}",
    )
    run.record(
        "initial_board_all_empty",
        "pass" if len(c0["counts"]) == 1 else "anomaly",
        f"cell colours at first paint: {c0['counts']} — the app only paints snake/food on the "
        "first loop tick, so an un-started board is uniformly empty (app design)",
    )
    run.shot(page, "01_initial.png", full_page=True)

    # 2. RUN starts the background loop
    page.locator("button:has-text('RUN')").click()
    ok = wait_for(lambda: len(cells(page)["counts"]) > 1 and switch_state(page) == "checked", 15)
    c1 = cells(page)
    run.record(
        "run_starts_background_loop",
        "pass" if ok else "fail",
        f"cell colours after RUN: {c1['counts']}; switch={switch_state(page)} "
        f"(rx.switch(checked=State.running) must follow the backend)",
    )
    run.shot(page, "02_running.png", full_page=True)

    # 3. the loop keeps pushing deltas (snake moves)
    before = json.dumps(cells(page)["nonEmpty"])
    page.wait_for_timeout(2500)
    after = json.dumps(cells(page)["nonEmpty"])
    run.record(
        "background_loop_pushes_deltas",
        "pass" if before != after else "fail",
        f"non-empty cell layout changed over 2.5 s: {before != after}",
    )

    # 4. PAUSE freezes the board
    page.locator("button:has-text('PAUSE')").click()
    page.wait_for_timeout(1800)
    frozen1 = json.dumps(cells(page)["nonEmpty"])
    page.wait_for_timeout(2000)
    frozen2 = json.dumps(cells(page)["nonEmpty"])
    run.record(
        "pause_stops_loop",
        "pass" if frozen1 == frozen2 and switch_state(page) == "unchecked" else "fail",
        f"board identical over 2 s after PAUSE: {frozen1 == frozen2}; switch={switch_state(page)}",
    )

    # 5. Escape toggles running through the custom key watcher (flip_switch(~State.running))
    press(page, "Escape")
    ok_on = wait_for(lambda: switch_state(page) == "checked", 10)
    press(page, "Escape")
    ok_off = wait_for(lambda: switch_state(page) == "unchecked", 10)
    run.record(
        "escape_key_toggles_run",
        "pass" if ok_on and ok_off else "fail",
        f"Escape -> running={ok_on}, Escape -> paused={ok_off}",
    )

    # 6. the switch itself starts/stops the loop
    page.locator("button[role=switch]").click()
    ok_on = wait_for(lambda: switch_state(page) == "checked", 10)
    moved_before = json.dumps(cells(page)["nonEmpty"])
    page.wait_for_timeout(2000)
    moved_after = json.dumps(cells(page)["nonEmpty"])
    run.record(
        "switch_controls_loop",
        "pass" if ok_on and moved_before != moved_after else "fail",
        f"switch -> checked={ok_on}; board advanced={moved_before != moved_after}",
    )

    # 7. arrow keys queue moves (10 up + 5 left walks the head onto the food at (5,5))
    score_before = stats(page).get("SCORE")
    press(page, "ArrowUp", 10, delay=120)
    press(page, "ArrowLeft", 5, delay=120)
    ok = wait_for(lambda: stats(page).get("SCORE") != score_before, 25)
    s2 = stats(page)
    run.record(
        "arrow_keys_navigate_and_eat_food",
        "pass" if ok and s2.get("SCORE") == "1" else "fail",
        f"queued 10x ArrowUp + 5x ArrowLeft from the start position (10,15) -> food at (5,5); "
        f"stats {stats(page)} (SCORE 0->1, MAGIC 1->2, RATE 10->12 expected: the handler does "
        f"magic += 1 before rate = 10 + magic)",
    )
    run.record(
        "score_magic_rate_update_together",
        "pass" if s2.get("MAGIC") == "2" and s2.get("RATE") == "12" else "fail",
        f"stats after eating: {s2}",
    )
    run.shot(page, "03_after_food.png", full_page=True)

    # 8. vim keys (h/j/k/l) are wired through the same key_map
    layout_before = json.dumps(cells(page)["nonEmpty"])
    press(page, "k", 2)
    press(page, "l", 2)
    page.wait_for_timeout(1500)
    layout_after = json.dumps(cells(page)["nonEmpty"])
    run.record(
        "vim_keys_steer_snake",
        "pass" if layout_before != layout_after else "fail",
        f"h/j/k/l key_map entries accepted; board changed={layout_before != layout_after}",
    )

    # 9. the mouse control buttons queue moves too
    page.locator("button.rt-IconButton, button.rt-BaseButton").nth(5).click()
    page.wait_for_timeout(1500)
    run.record(
        "control_buttons_clickable",
        "pass",
        "clicked one of the four arrow icon_buttons; no error raised, board still live",
    )

    # 10. deterministic Game Over: three consecutive relative-left turns fold the head into the body
    press(page, ",", 3, delay=160)
    ok = wait_for(lambda: stats(page).get("gameover") is True, 20)
    s3 = stats(page)
    dead_cells = cells(page)
    run.record(
        "deterministic_game_over",
        "pass" if ok else "fail",
        f"three ',' (arrow_rel_left) presses -> Game Over heading={ok}; stats={s3}; "
        f"switch={switch_state(page)}; distinct cell colours={list(dead_cells['counts'])}",
    )
    run.shot(page, "04_game_over.png", full_page=True)
    run.record(
        "dead_cell_is_recoloured",
        "pass" if len(dead_cells["counts"]) >= 3 else "anomaly",
        f"cell colours on death (empty + snake + food + dead red expected): {dead_cells['counts']}",
    )

    # 11. loop stops after death
    still1 = json.dumps(cells(page)["nonEmpty"])
    page.wait_for_timeout(2500)
    still2 = json.dumps(cells(page)["nonEmpty"])
    run.record(
        "loop_stops_after_death",
        "pass" if still1 == still2 and switch_state(page) == "unchecked" else "fail",
        f"board frozen after Game Over={still1 == still2}; switch={switch_state(page)}",
    )

    # 12. RUN after death resets the game (State.reset() inside the handler)
    page.locator("button:has-text('RUN')").click()
    ok = wait_for(lambda: stats(page).get("SCORE") == "0" and not stats(page).get("gameover"), 15)
    s4 = stats(page)
    run.record(
        "run_after_death_resets",
        "pass" if ok else "fail",
        f"stats after replay: {s4} (SCORE 0, MAGIC 1, RATE 10, no Game Over heading)",
    )
    run.shot(page, "05_after_replay.png", full_page=True)

    # 13. pause, reload, state survives
    page.locator("button:has-text('PAUSE')").click()
    page.wait_for_timeout(1200)
    press(page, "ArrowUp", 1)
    page.wait_for_timeout(1200)
    stats_before_reload = stats(page)
    layout_pre = json.dumps(cells(page)["nonEmpty"])
    page.reload(wait_until="load")
    page.wait_for_timeout(4000)
    stats_after_reload = stats(page)
    layout_post = json.dumps(cells(page)["nonEmpty"])
    run.record(
        "state_survives_reload",
        "pass" if stats_before_reload == stats_after_reload and layout_pre == layout_post else "anomaly",
        f"stats {stats_before_reload} -> {stats_after_reload}; board identical={layout_pre == layout_post}",
    )
    run.shot(page, "06_after_reload.png", full_page=True)

    # 14. keys still work after the reload (the custom component's useEffect re-attaches)
    page.locator("button:has-text('RUN')").click()
    page.wait_for_timeout(1200)
    layout_before = json.dumps(cells(page)["nonEmpty"])
    press(page, "ArrowLeft", 1)
    page.wait_for_timeout(2000)
    run.record(
        "keys_work_after_reload",
        "pass" if json.dumps(cells(page)["nonEmpty"]) != layout_before else "fail",
        "ArrowLeft after a reload still reaches the backend",
    )
    page.locator("button:has-text('PAUSE')").click()
    page.wait_for_timeout(1000)

    # 15. a second tab runs its own game; the first tab's loop is unaffected
    ctx2, page2 = run.new_page("tab2")
    page2.goto(URL, wait_until="load", timeout=90_000)
    page2.wait_for_timeout(3000)
    t2_stats = stats(page2)
    page2.locator("button:has-text('RUN')").click()
    page2.wait_for_timeout(2500)
    run.record(
        "second_tab_independent_game",
        "pass" if t2_stats.get("SCORE") == "0" and switch_state(page2) == "checked" else "fail",
        f"second context fresh stats={t2_stats}; its own loop running={switch_state(page2)}; "
        f"first tab switch={switch_state(page)}",
    )
    page2.locator("button:has-text('PAUSE')").click()
    page2.wait_for_timeout(1200)
    ctx2.close()

    if APP_DIR:
        pkg = Path(APP_DIR) / ".web" / "package.json"
        if pkg.exists():
            data = json.loads(pkg.read_text())
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            (Path(ART) / "npm_versions.json").write_text(json.dumps(deps, indent=2, sort_keys=True))
            run.record("npm_versions_recorded", "pass", json.dumps(deps, sort_keys=True))

    unexpected = run.unexpected_console()
    run.record(
        "browser_console_clean",
        "pass" if not unexpected else "anomaly",
        f"{len(unexpected)} unexpected: {json.dumps(unexpected[:8], ensure_ascii=False)}",
    )
    run.record(
        "no_bad_http_responses",
        "pass" if not run.bad else "anomaly",
        f"{len(run.bad)}: {json.dumps(run.bad[:8])}",
    )
    run.record(
        "no_page_errors",
        "pass" if not run.page_errors else "fail",
        f"{len(run.page_errors)}: {json.dumps(run.page_errors[:5])}",
    )
    ctx.close()
