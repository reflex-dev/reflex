"""Two independent browser sessions each start background tasks; check isolation.

usage: probe_two_sessions.py <frontend_url> <artifacts_dir> <label>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from drive_common import Run, wait_for  # noqa: E402

TASKS_JS = """
() => Array.from(document.querySelectorAll("div[role='progressbar']")).map(pb => {
  const row = pb.closest('.rx-Stack');
  return {id: row.querySelector('p').textContent, value: +pb.getAttribute('aria-valuenow')};
});
"""


def main():
    url = sys.argv[1].rstrip("/") + "/"
    with Run(sys.argv[2], sys.argv[3]) as run:
        ctx_a, a = run.new_page(tag="A")
        ctx_b, b = run.new_page(tag="B")
        for pg in (a, b):
            pg.set_default_timeout(15000)
            pg.goto(url, wait_until="networkidle")
            pg.wait_for_timeout(1000)
        a.get_by_role("button", name="➕ New Task").click()
        a.get_by_role("button", name="➕ New Task").click()
        b.get_by_role("button", name="➕ New Task").click()
        wait_for(lambda: len(a.evaluate(TASKS_JS)) == 2, 10)
        wait_for(lambda: len(b.evaluate(TASKS_JS)) == 1, 10)
        ta, tb = a.evaluate(TASKS_JS), b.evaluate(TASKS_JS)
        run.record(
            "sessions_see_only_own_tasks",
            "pass" if len(ta) == 2 and len(tb) == 1 else "fail",
            f"session_A_cards={len(ta)} session_B_cards={len(tb)} A_ids={[t['id'] for t in ta]} B_ids={[t['id'] for t in tb]}",
        )
        before_a = {t["id"]: t["value"] for t in ta}
        before_b = {t["id"]: t["value"] for t in tb}
        a.wait_for_timeout(2500)
        after_a = {t["id"]: t["value"] for t in a.evaluate(TASKS_JS)}
        after_b = {t["id"]: t["value"] for t in b.evaluate(TASKS_JS)}
        moved_a = sum(1 for i in before_a if after_a.get(i, -1) > before_a[i])
        moved_b = sum(1 for i in before_b if after_b.get(i, -1) > before_b[i])
        run.record(
            "both_sessions_stream_concurrently",
            "pass" if moved_a == len(before_a) and moved_b == len(before_b) else "fail",
            f"A_advanced={moved_a}/{len(before_a)} B_advanced={moved_b}/{len(before_b)}",
        )
        run.shot(a, "two_sessions_A.png")
        run.shot(b, "two_sessions_B.png")
        unexpected = run.unexpected_console()
        run.record("no_unexpected_console", "pass" if not unexpected else "anomaly", str(unexpected)[:500])
        ctx_a.close(); ctx_b.close()


main()
