"""Drive the reflex-examples `lorem-stream` app (background streaming tasks) end to end.

usage: drive_lorem.py <frontend_url> <artifacts_dir> <label> [<app_dir>]

Every check is recorded in <artifacts_dir>/results.json with a status
(pass/fail/anomaly) and a details string kept free of random values so runs on
different reflex versions can be diffed directly.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from drive_common import Run, wait_for  # noqa: E402

ROW = "div.rx-Stack:has(> div.rt-Box > div[role='progressbar'])"

TASKS_JS = """
() => Array.from(document.querySelectorAll("div[role='progressbar']")).map(pb => {
  const row = pb.closest('.rx-Stack');
  const card = row.parentElement;
  const ps = Array.from(card.children).filter(e => e.tagName === 'P');
  return {
    id: row.querySelector('p').textContent,
    value: +pb.getAttribute('aria-valuenow'),
    max: +pb.getAttribute('aria-valuemax'),
    state: pb.getAttribute('data-state'),
    btns: Array.from(row.querySelectorAll('button')).map(b => b.textContent),
    text_len: ps.length ? ps[ps.length - 1].textContent.length : 0,
  };
});
"""


def tasks(page):
    return page.evaluate(TASKS_JS)


def by_id(page, tid):
    for i, t in enumerate(tasks(page)):
        if t["id"] == str(tid):
            return i, t
    return None, None


def new_task(page):
    page.get_by_role("button", name="➕ New Task").click()


def main():
    url = sys.argv[1].rstrip("/") + "/"
    art = sys.argv[2]
    label = sys.argv[3]
    app_dir = sys.argv[4] if len(sys.argv) > 4 else None

    with Run(art, label) as run:
        ctx, page = run.new_page()
        page.set_default_timeout(15000)

        # 1. index loads with no tasks
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(1200)
        run.shot(page, "01_index.png")
        n0 = len(tasks(page))
        run.record(
            "index_loads",
            "pass" if page.get_by_role("button", name="➕ New Task").is_visible() and n0 == 0 else "fail",
            f"new_task_button_visible=True cards={n0}",
        )

        # 2. one background task streams
        new_task(page)
        ok = wait_for(lambda: len(tasks(page)) == 1, 10)
        t0 = tasks(page)[0] if ok else None
        first_len = t0["text_len"] if t0 else 0
        first_val = t0["value"] if t0 else 0
        time.sleep(2.0)
        _, t0b = by_id(page, 0)
        grew = bool(t0b and t0b["text_len"] > first_len and t0b["value"] > first_val)
        in_range = bool(t0b and 7 <= t0b["max"] <= 12)
        run.record(
            "new_task_streams",
            "pass" if ok and grew and in_range else "fail",
            f"card_appeared={ok} grew={grew} max_in_ITERATIONS_RANGE={in_range} toggle_btn={t0b['btns'][0] if t0b else None}",
        )
        run.shot(page, "02_one_task.png")

        # 3. three concurrent tasks all advance in the same window
        new_task(page)
        new_task(page)
        wait_for(lambda: len(tasks(page)) == 3, 10)
        before = {t["id"]: t for t in tasks(page)}
        time.sleep(2.0)
        after = {t["id"]: t for t in tasks(page)}
        advanced = [
            i for i in before
            if i in after and (after[i]["value"] > before[i]["value"] or before[i]["state"] == "complete")
        ]
        run.record(
            "three_concurrent_tasks",
            "pass" if len(before) == 3 and len(advanced) == 3 else "fail",
            f"cards={len(before)} advanced_or_complete={len(advanced)} ids={sorted(before)}",
        )
        run.shot(page, "03_three_tasks.png")

        # 4. pause one running task; it freezes, the others keep going
        running = [t for t in tasks(page) if t["state"] != "complete"]
        if not running:
            run.record("pause_freezes_stream", "skipped", "no running task left to pause")
            run.record("pause_leaves_others_running", "skipped", "no running task left to pause")
            paused_id = None
        else:
            paused_id = running[0]["id"]
            idx, _ = by_id(page, paused_id)
            page.locator(ROW).nth(idx).locator("button").nth(0).click()
            time.sleep(0.8)
            _, p1 = by_id(page, paused_id)
            others_before = {t["id"]: t for t in tasks(page) if t["id"] != paused_id}
            time.sleep(2.5)
            _, p2 = by_id(page, paused_id)
            frozen = bool(p1 and p2 and p1["value"] == p2["value"] and p1["text_len"] == p2["text_len"])
            others_after = {t["id"]: t for t in tasks(page) if t["id"] != paused_id}
            others_moved = [
                i for i in others_before
                if others_after[i]["value"] > others_before[i]["value"]
                or others_before[i]["state"] == "complete"
            ]
            run.record(
                "pause_freezes_stream",
                "pass" if frozen else "fail",
                f"task={paused_id} frozen={frozen} progress_at_pause_equals_after=True",
            )
            run.record(
                "pause_leaves_others_running",
                "pass" if len(others_moved) == len(others_before) else "fail",
                f"others={len(others_before)} still_advancing_or_complete={len(others_moved)}",
            )
            run.shot(page, "04_paused.png")

            # 5. resume continues from the paused progress (does not restart)
            _, p3 = by_id(page, paused_id)
            idx, _ = by_id(page, paused_id)
            page.locator(ROW).nth(idx).locator("button").nth(0).click()
            resumed = wait_for(
                lambda: (by_id(page, paused_id)[1] or {}).get("value", -1) > p3["value"], 8
            )
            _, p4 = by_id(page, paused_id)
            kept_text = bool(p4 and p4["text_len"] >= p3["text_len"])
            run.record(
                "resume_continues_from_progress",
                "pass" if resumed and kept_text else "fail",
                f"task={paused_id} progress_increased={resumed} text_kept={kept_text}",
            )

        # 6. a task runs to completion and flips to the restart button
        done = wait_for(
            lambda: any(t["state"] == "complete" and t["btns"][0] == "🔄" for t in tasks(page)), 25
        )
        comp = [t for t in tasks(page) if t["state"] == "complete"]
        run.record(
            "task_completes_and_shows_restart",
            "pass" if done else "fail",
            f"completed_cards={len(comp)} restart_button={'🔄' if done else None} value_eq_max={all(t['value'] == t['max'] for t in comp)}",
        )
        run.shot(page, "05_complete.png")

        # 7. restart a completed task: progress resets and it streams again
        if comp:
            rid = comp[0]["id"]
            idx, _ = by_id(page, rid)
            page.locator(ROW).nth(idx).locator("button").nth(0).click()
            reset = wait_for(lambda: (by_id(page, rid)[1] or {}).get("value", -1) <= 1, 8)
            _, r1 = by_id(page, rid)
            time.sleep(1.6)
            _, r2 = by_id(page, rid)
            regrew = bool(r1 and r2 and r2["value"] >= r1["value"] and r2["text_len"] > 0)
            new_max_ok = bool(r2 and 7 <= r2["max"] <= 12)
            run.record(
                "restart_completed_task",
                "pass" if reset and regrew and new_max_ok else "fail",
                f"task={rid} progress_reset={reset} streams_again={regrew} new_max_in_range={new_max_ok}",
            )
            run.shot(page, "06_restarted.png")
        else:
            run.record("restart_completed_task", "skipped", "no completed task")

        # 8. kill removes the card
        cards = tasks(page)
        kid = cards[-1]["id"]
        idx, _ = by_id(page, kid)
        page.locator(ROW).nth(idx).locator("button").nth(1).click()
        gone = wait_for(lambda: by_id(page, kid)[1] is None, 8)
        run.record(
            "kill_removes_card",
            "pass" if gone and len(tasks(page)) == len(cards) - 1 else "fail",
            f"killed={kid} card_removed={gone} cards_before={len(cards)} cards_after={len(tasks(page))}",
        )
        run.shot(page, "07_killed.png")

        # 9. reload keeps state and a running task keeps streaming into the new page
        n_before = len(tasks(page))
        new_task(page)
        wait_for(lambda: len(tasks(page)) > n_before, 10)
        wait_for(lambda: any(t["state"] != "complete" for t in tasks(page)), 8)
        pre = {t["id"]: t for t in tasks(page)}
        running_ids = [i for i, t in pre.items() if t["state"] != "complete"]
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(1500)
        post = {t["id"]: t for t in tasks(page)}
        same_ids = sorted(pre) == sorted(post)
        text_kept = all(post[i]["text_len"] >= pre[i]["text_len"] for i in pre if i in post)
        run.record(
            "state_survives_reload",
            "pass" if same_ids and text_kept else "fail",
            f"same_task_ids={same_ids} text_preserved={text_kept} cards={len(post)}",
        )
        run.shot(page, "08_after_reload.png")
        if running_ids:
            rid = running_ids[0]
            base = post.get(rid, {}).get("value", -1)
            streamed = wait_for(
                lambda: (by_id(page, rid)[1] or {}).get("value", -1) > base
                or (by_id(page, rid)[1] or {}).get("state") == "complete",
                12,
            )
            run.record(
                "background_task_streams_into_reloaded_page",
                "pass" if streamed else "fail",
                f"task={rid} received_delta_after_reload={streamed}",
            )
        else:
            run.record("background_task_streams_into_reloaded_page", "skipped", "no running task at reload")

        # 10. burst: six new tasks clicked as fast as possible all stream
        base_ids = {t["id"] for t in tasks(page)}
        for _ in range(6):
            new_task(page)
        appeared = wait_for(lambda: len(tasks(page)) >= len(base_ids) + 6, 15)
        burst = [t for t in tasks(page) if t["id"] not in base_ids]
        time.sleep(2.0)
        after_burst = {t["id"]: t for t in tasks(page)}
        moved = [t["id"] for t in burst if after_burst[t["id"]]["value"] > 0]
        run.record(
            "burst_six_tasks_all_stream",
            "pass" if appeared and len(moved) == 6 else "fail",
            f"new_cards={len(burst)} streaming={len(moved)}",
        )
        run.shot(page, "09_burst.png", full_page=True)

        # 11. kill every task from the burst; page ends clean
        for t in burst:
            idx, _ = by_id(page, t["id"])
            if idx is not None:
                page.locator(ROW).nth(idx).locator("button").nth(1).click()
                page.wait_for_timeout(150)
        emptied = wait_for(lambda: not ({t["id"] for t in tasks(page)} & {t["id"] for t in burst}), 10)
        run.record(
            "kill_all_burst_tasks",
            "pass" if emptied else "fail",
            f"all_burst_cards_removed={emptied} remaining_cards={len(tasks(page))}",
        )
        run.shot(page, "10_final.png", full_page=True)

        # 12. console / network hygiene
        unexpected = run.unexpected_console()
        run.record(
            "no_unexpected_console",
            "pass" if not unexpected else "anomaly",
            json.dumps(unexpected)[:600],
        )
        run.record(
            "no_failed_or_4xx_requests",
            "pass" if not run.bad else "anomaly",
            json.dumps(run.bad)[:600],
        )
        run.record(
            "no_page_errors",
            "pass" if not run.page_errors else "fail",
            json.dumps(run.page_errors)[:600],
        )

        if app_dir:
            pkg = Path(app_dir) / ".web" / "package.json"
            if pkg.exists():
                (Path(art) / "package.json").write_text(pkg.read_text())
            lock = Path(app_dir) / "reflex.lock" / "bun.lock"
            if lock.exists():
                (Path(art) / "bun.lock").write_text(lock.read_text())
            try:
                out = subprocess.run(
                    ["/usr/bin/find", str(Path(app_dir) / ".web" / "utils"), "-maxdepth", "1", "-name", "context.*"],
                    capture_output=True, text=True, timeout=20,
                ).stdout
                (Path(art) / "context_files.txt").write_text(out)
            except Exception as exc:  # noqa: BLE001
                (Path(art) / "context_files.txt").write_text(f"error: {exc}")
        ctx.close()


main()
