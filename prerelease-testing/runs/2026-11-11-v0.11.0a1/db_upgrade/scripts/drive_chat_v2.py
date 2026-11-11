"""Drive reflex-examples chat_v2 with the QA LLM stub (server must run with AI_PROVIDER=qa_stub).

Usage: drive_chat_v2.py <url> <outdir> <tag> <prompt> [expect_prev_prompt ...]
Checks: page renders, previous interactions (from sqlite, on_load) listed, a new prompt streams the stub's
tokens through the background task, the answer persists across a reload (chatinteraction row).
"""

import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from harness import CHROMIUM, Run, guard_driver_python, wait_for  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

guard_driver_python()
URL, OUT, TAG, PROMPT = sys.argv[1:5]
PREV = sys.argv[5:]
run = Run(TAG, OUT)


def body(page):
    try:
        return page.inner_text("body")
    except Exception:  # noqa: BLE001
        return ""


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROMIUM)
    ctx = b.new_context(viewport={"width": 1280, "height": 1000})
    page = ctx.new_page()
    run.attach(page)
    page.goto(URL, wait_until="load")
    ta = page.locator('textarea[placeholder="How can I help?"]')
    try:
        ta.wait_for(timeout=40000)
        run.check("page renders input box", True)
    except Exception as e:  # noqa: BLE001
        run.check("page renders input box", False, e)
    wait_for(lambda: "An error occurred" not in body(page), 3)
    time.sleep(3)  # on_load -> load_messages_from_database
    txt = body(page)
    for prev in PREV:
        run.check(f"previous interaction from DB listed: {prev!r}", prev in txt, txt[-400:])
    run.shot(page, "loaded")
    ta.fill(PROMPT)
    time.sleep(0.5)
    t0 = time.time()
    ta.press("Enter")
    seen_partial = wait_for(lambda: "Stubbed" in body(page) and "done." not in body(page), 8, 0.05)
    run.check("streaming: partial answer visible before completion", bool(seen_partial))
    done = wait_for(lambda: f"answer to: {PROMPT}" in body(page) and "done." in body(page), 25)
    run.check("streaming: full stub answer rendered", bool(done), f"{time.time()-t0:.1f}s")
    run.shot(page, "answered")
    run.check("input cleared after submit", ta.input_value() == "", ta.input_value())
    time.sleep(2)  # _save_resulting_chat_interaction runs after the async-with block
    page.reload(wait_until="load")
    ta.wait_for(timeout=30000)
    ok = wait_for(lambda: PROMPT in body(page) and "done." in body(page), 15)
    run.check("reload: new interaction persisted + reloaded from DB", bool(ok))
    run.shot(page, "reloaded")
    run.notes["body_tail"] = body(page)[-1500:]
    ctx.close()
    b.close()
sys.exit(run.finish())
