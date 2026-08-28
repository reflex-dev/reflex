"""Playwright driver for lorem-stream example app.

Usage: python drive_lorem.py <label> <frontend_url>
Saves screenshots + console/network logs to ./artifacts/<label>_*.
Exercises: create 3 concurrent streaming tasks, verify incremental text growth,
pause/resume a task, kill a task, restart a completed task.
"""

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

LABEL = sys.argv[1]
URL = sys.argv[2]
ART = Path(__file__).parent / "artifacts"
ART.mkdir(exist_ok=True)

console_msgs = []
failed_requests = []
results = []


def check(name, ok, detail=""):
    results.append({"name": name, "ok": bool(ok), "detail": detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}")


def task_cards(page):
    # card = vstack ancestor of each progress bar (progress > rt-Box > hstack > card)
    return page.locator(".rt-ProgressRoot").locator("xpath=ancestor::div[3]")


def get_stream_texts(page):
    """Return list of streamed text content per task card (direct-child <p>)."""
    out = []
    cards = task_cards(page)
    for i in range(cards.count()):
        out.append(cards.nth(i).locator("xpath=./p").inner_text())
    return out


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    page.on(
        "console",
        lambda m: console_msgs.append({"type": m.type, "text": m.text}),
    )
    page.on(
        "requestfailed",
        lambda r: failed_requests.append({"url": r.url, "failure": str(r.failure)}),
    )
    page.on(
        "response",
        lambda r: failed_requests.append({"url": r.url, "status": r.status})
        if r.status >= 400
        else None,
    )

    page.goto(URL, wait_until="load")
    new_task = page.get_by_role("button", name="New Task")
    new_task.wait_for(state="visible", timeout=30000)
    page.screenshot(path=str(ART / f"{LABEL}_lorem_initial.png"))
    check("page loads, New Task button visible", True)

    # start 3 concurrent tasks
    for _ in range(3):
        new_task.click()
        time.sleep(0.3)
    try:
        page.wait_for_function(
            "document.querySelectorAll('.rt-ProgressRoot').length >= 3",
            timeout=15000,
        )
        check("3 task cards appear", True)
    except Exception as e:
        check("3 task cards appear", False, str(e))

    time.sleep(1.2)
    texts_a = get_stream_texts(page)
    time.sleep(2.0)
    texts_b = get_stream_texts(page)
    growth = [
        len(b) > len(a) for a, b in zip(texts_a, texts_b)
    ]
    check(
        "all 3 tasks stream text concurrently (text grows over 2s)",
        len(texts_a) == 3 and all(growth),
        f"lens {[len(t) for t in texts_a]} -> {[len(t) for t in texts_b]}",
    )
    page.screenshot(path=str(ART / f"{LABEL}_lorem_streaming.png"))

    # wait for all 3 tasks to complete (7-12 iterations * 0.5s each)
    try:
        page.wait_for_function(
            """() => [...document.querySelectorAll('button')]
                    .filter(b => b.textContent.includes('🔄')).length >= 3""",
            timeout=30000,
        )
        check("all 3 tasks run to completion (🔄 restart buttons shown)", True)
    except Exception as e:
        check("all 3 tasks run to completion (🔄 restart buttons shown)", False, str(e))
    page.screenshot(path=str(ART / f"{LABEL}_lorem_completed.png"))

    # restart the first (topmost) completed task: text resets and streams again
    cards = task_cards(page)
    old_text = get_stream_texts(page)[0]
    toggle_btn = cards.nth(0).get_by_role("button").first
    toggle_btn.click()
    time.sleep(2.0)
    new_text = get_stream_texts(page)[0]
    check(
        "restarting completed task resets text and streams",
        0 < len(new_text) < len(old_text) or (new_text and new_text != old_text),
        f"old len {len(old_text)}, new len {len(new_text)}",
    )

    # pause the (now running, just restarted) task quickly, verify growth stops
    toggle_btn.click()
    time.sleep(1.2)  # allow in-flight iteration to land
    t0 = get_stream_texts(page)[0]
    time.sleep(2.0)
    t1 = get_stream_texts(page)[0]
    check("paused task stops streaming", t0 == t1, f"len {len(t0)} vs {len(t1)}")

    # resume it
    toggle_btn.click()
    time.sleep(2.0)
    t2 = get_stream_texts(page)[0]
    check("resumed task streams again", len(t2) > len(t1), f"len {len(t1)} -> {len(t2)}")

    # kill the second card, count decreases
    n_before = task_cards(page).count()
    task_cards(page).nth(1).get_by_role("button", name="❌").click()
    time.sleep(1.0)
    n_after = task_cards(page).count()
    check("kill removes a task card", n_after == n_before - 1, f"{n_before} -> {n_after}")
    page.screenshot(path=str(ART / f"{LABEL}_lorem_final.png"))

    time.sleep(1)
    browser.close()

(ART / f"{LABEL}_lorem_console.json").write_text(json.dumps(console_msgs, indent=2))
(ART / f"{LABEL}_lorem_netfail.json").write_text(
    json.dumps([f for f in failed_requests if f], indent=2)
)
(ART / f"{LABEL}_lorem_results.json").write_text(json.dumps(results, indent=2))

unexpected = [
    m
    for m in console_msgs
    if m["type"] in ("error", "warning")
    and "HydrateFallback" not in m["text"]
    and "React DevTools" not in m["text"]
    and "[vite] connecting" not in m["text"]
    and "[vite] connected" not in m["text"]
]
print(f"\nconsole: {len(console_msgs)} msgs, {len(unexpected)} unexpected err/warn")
for m in unexpected:
    print("  UNEXPECTED:", m["type"], m["text"][:300])
print(f"failed/4xx+ requests: {[f for f in failed_requests if f]}")
print("ALL_OK" if all(r["ok"] for r in results) else "SOME_FAILED")
