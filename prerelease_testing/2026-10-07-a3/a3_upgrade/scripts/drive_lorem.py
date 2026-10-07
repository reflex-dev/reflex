"""Drive the reflex-examples `lorem-stream` app (background tasks streaming via `async with self`).

Usage: drive_lorem.py <url> <outdir> <tag>
Flows: 3 concurrent streams, completion (🔄), restart, pause/resume, kill, reload mid-stream (bg tasks
keep running server-side and the reconnected tab keeps receiving), a 2nd tab (new token = own state),
and a "duplicated tab" (new context seeded with tab 1's sessionStorage token -> server issues new_token).
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from harness import CHROMIUM, Run, guard_driver_python  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

guard_driver_python()
URL, OUT, TAG = sys.argv[1:4]
run = Run(TAG, OUT)

TASKS_JS = """() => [...document.querySelectorAll('.rt-ProgressRoot')].map(pr => {
    const card = pr.parentElement.parentElement.parentElement;
    const btns = [...card.querySelectorAll('button')];
    const ps = card.querySelectorAll(':scope > p');
    const txt = ps.length ? ps[ps.length - 1].innerText : '';
    return {id: pr.parentElement.querySelector('p').innerText.trim(), len: txt.length,
            toggle: btns[0] ? btns[0].innerText.trim() : null,
            now: pr.getAttribute('aria-valuenow'), max: pr.getAttribute('aria-valuemax')};
})"""


def tasks(page):
    return page.evaluate(TASKS_JS)


def pump(page, cond, timeout=15.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        page.wait_for_timeout(200)
    return bool(cond())


def by_id(page, tid):
    return next((t for t in tasks(page) if t["id"] == tid), None)


def card_btn(page, tid, which):
    """which: 0 = toggle (⏯️/🔄), 1 = kill (❌)"""
    page.evaluate("""([tid, which]) => {
        for (const pr of document.querySelectorAll('.rt-ProgressRoot')) {
            if (pr.parentElement.querySelector('p').innerText.trim() === tid) {
                pr.parentElement.parentElement.parentElement.querySelectorAll('button')[which].click(); return;
            }
        }
        throw new Error('no card ' + tid);
    }""", [tid, which])


def grows(page, ids, wait=2.0):
    a = {t["id"]: t["len"] for t in tasks(page)}
    page.wait_for_timeout(int(wait * 1000))
    b = {t["id"]: t["len"] for t in tasks(page)}
    return all(b.get(i, 0) > a.get(i, 0) for i in ids), a, b


def token(page):
    return page.evaluate("() => window.sessionStorage.getItem('token')")


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM)
    ctx = browser.new_context(viewport={"width": 1300, "height": 950})
    page = ctx.new_page()
    run.attach(page, "tab1")
    page.goto(URL, wait_until="load")
    nt = page.get_by_role("button", name="New Task")
    nt.wait_for(timeout=60000)
    page.wait_for_timeout(1000)
    run.check("A: page loads with no tasks", tasks(page) == [], tasks(page))
    for _ in range(3):
        nt.click()
        page.wait_for_timeout(150)
    ok = pump(page, lambda: len(tasks(page)) == 3, 10)
    ids = [t["id"] for t in tasks(page)]
    run.check("B: 3 task cards appear (task_ids newest first)", ok and ids == ["2", "1", "0"], tasks(page))
    g, a, b = grows(page, ids)
    run.check("C: all 3 stream concurrently (text grows over 2 s)", g, f"{a} -> {b}")
    run.shot(page, "01_streaming")
    ok = pump(page, lambda: len(tasks(page)) == 3 and all(t["toggle"] == "🔄" for t in tasks(page)), 15)
    run.check("D: all 3 run to completion (🔄, progress == max)", ok and all(t["now"] == t["max"] for t in tasks(page)), tasks(page))
    before = by_id(page, "1")
    card_btn(page, "1", 0)
    ok = pump(page, lambda: (by_id(page, "1") or {}).get("toggle") == "⏯️", 5)
    page.wait_for_timeout(1200)
    after = by_id(page, "1")
    run.check("E: restart a completed task resets and streams again", ok and 0 < after["len"] < before["len"] or (ok and after["now"] not in (None, before["now"])),
              f"{before} -> {after}")
    card_btn(page, "1", 0)  # pause
    page.wait_for_timeout(1200)
    t0 = by_id(page, "1")
    page.wait_for_timeout(2000)
    t1 = by_id(page, "1")
    run.check("F: paused task stops streaming", t0["len"] == t1["len"] and t1["toggle"] == "⏯️", f"{t0} -> {t1}")
    card_btn(page, "1", 0)  # resume
    g, a, b = grows(page, ["1"], 1.5)
    run.check("G: resumed task streams again", g, f"{a.get('1')} -> {b.get('1')}")
    ok = pump(page, lambda: (by_id(page, "1") or {}).get("toggle") == "🔄", 10)
    run.check("G2: resumed task completes", ok, by_id(page, "1"))
    card_btn(page, "0", 1)  # kill
    ok = pump(page, lambda: [t["id"] for t in tasks(page)] == ["2", "1"], 5)
    run.check("H: kill removes the card", ok, [t["id"] for t in tasks(page)])
    run.shot(page, "02_after_kill")
    # reload mid-stream
    nt.click(); page.wait_for_timeout(150); nt.click()
    pump(page, lambda: len(tasks(page)) == 4, 8)
    page.wait_for_timeout(800)
    mid = {t["id"]: t["len"] for t in tasks(page)}
    tok1 = token(page)
    page.reload(wait_until="load")
    page.get_by_role("button", name="New Task").wait_for(timeout=30000)
    pump(page, lambda: len(tasks(page)) == 4, 10)
    run.notes["after_reload_tasks"] = tasks(page)
    g, a, b = grows(page, ["3", "4"], 1.5)
    run.check("I: after reload mid-stream the running bg tasks keep streaming into the tab", g and token(page) == tok1, f"before reload {mid}; {a} -> {b}")
    ok = pump(page, lambda: all(t["toggle"] == "🔄" for t in tasks(page)), 15)
    fin = {t["id"]: (t["now"], t["max"]) for t in tasks(page)}
    run.check("I2: streams started before the reload complete (progress == max)", ok and all(n == m for n, m in fin.values()), fin)
    run.shot(page, "03_after_reload")
    # second tab: new sessionStorage token = separate state
    page2 = ctx.new_page()
    run.attach(page2, "tab2")
    page2.goto(URL, wait_until="load")
    page2.get_by_role("button", name="New Task").wait_for(timeout=30000)
    page2.wait_for_timeout(1000)
    tok2 = token(page2)
    run.check("J: 2nd tab has its own token and an empty task list", tok2 and tok2 != tok1 and tasks(page2) == [], f"tok1={tok1} tok2={tok2} tasks={tasks(page2)}")
    page2.get_by_role("button", name="New Task").click()
    ok = pump(page2, lambda: len(tasks(page2)) == 1, 5)
    g2, _, _ = grows(page2, ["0"], 1.5)
    run.check("J2: 2nd tab streams its own task; tab 1 unaffected", ok and g2 and len(tasks(page)) == 4, f"tab2={tasks(page2)} tab1_count={len(tasks(page))}")
    # duplicated tab: same token as tab 1 in another context
    ctx3 = browser.new_context(viewport={"width": 1300, "height": 950})
    ctx3.add_init_script(f"if (!window.sessionStorage.getItem('token')) window.sessionStorage.setItem('token', {json.dumps(tok1)});")
    page3 = ctx3.new_page()
    run.attach(page3, "dup")
    page3.goto(URL, wait_until="load")
    page3.get_by_role("button", name="New Task").wait_for(timeout=30000)
    page3.wait_for_timeout(2000)
    tok3 = token(page3)
    run.notes["dup_tab"] = {"tok1": tok1, "tok3": tok3, "tasks": tasks(page3)}
    run.check("K: duplicated-token tab gets a new_token and its own (empty) state", tok3 != tok1 and tasks(page3) == [],
              f"tok3={tok3} same_as_tab1={tok3 == tok1} tasks={tasks(page3)}")
    nt.click()
    ok = pump(page, lambda: len(tasks(page)) == 5, 5)
    g, a, b = grows(page, [tasks(page)[0]["id"]] if tasks(page) else [], 1.5)
    run.check("K2: tab 1 still works after the duplicate connected", ok and g and token(page) == tok1, f"{len(tasks(page))} tasks, tok={token(page) == tok1}")
    run.check("K3: duplicated tab shows none of tab 1's tasks afterwards", tasks(page3) == [], tasks(page3))
    run.shot(page3, "04_dup_tab")
    run.shot(page, "05_tab1_final")
    browser.close()
sys.exit(run.finish())
