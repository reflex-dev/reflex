"""Drive the reflex-examples `quiz` app: radios, checkboxes, submit, redirect,
results page, back-navigation and on_load reset. Exercises router vars (#7068).

usage: drive_quiz.py <frontend_url> <label> <shots_dir>
"""

import json
import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1].rstrip("/")
LABEL = sys.argv[2]
SHOTS = sys.argv[3]

console, page_errors, failed, bad = [], [], [], []
r = {}

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = browser.new_context(viewport={"width": 1280, "height": 1000}).new_page()
    page.on("console", lambda m: console.append({"type": m.type, "text": m.text}))
    page.on("pageerror", lambda e: page_errors.append(str(e)))
    page.on("requestfailed", lambda q: failed.append(f"{q.method} {q.url} :: {q.failure}"))
    page.on("response", lambda x: bad.append(f"{x.status} {x.url}") if x.status >= 400 else None)

    page.goto(URL + "/", wait_until="networkidle", timeout=90_000)
    page.wait_for_timeout(2500)
    r["title"] = page.title()
    r["heading"] = page.locator("h1,h2,h3").first.inner_text()
    # rx.code_block on question 2 must render highlighted code
    r["code_block_present"] = page.locator("pre").count() > 0
    r["code_block_text"] = (
        page.locator("pre").first.inner_text()[:40] if page.locator("pre").count() else None
    )
    page.screenshot(path=f"{SHOTS}/{LABEL}_01_quiz.png", full_page=True)

    # Q1: pick the correct answer "False"
    radios = page.get_by_role("radio")
    r["radio_count"] = radios.count()
    page.get_by_role("radio", name="False").first.click()
    page.wait_for_timeout(500)
    # Q2: correct answer "[10, 20, 30, 40]"
    page.get_by_role("radio", name="[10, 20, 30, 40]").first.click()
    page.wait_for_timeout(500)
    # Q3: tick the 3 correct checkboxes (indices 2,3,4)
    cbs = page.get_by_role("checkbox")
    r["checkbox_count"] = cbs.count()
    for i in (2, 3, 4):
        cbs.nth(i).click()
        page.wait_for_timeout(250)
    page.wait_for_timeout(800)
    page.screenshot(path=f"{SHOTS}/{LABEL}_02_answered.png", full_page=True)

    # Submit -> rx.redirect("/result")
    page.get_by_role("button", name="Submit").click()
    page.wait_for_timeout(3000)
    r["url_after_submit"] = page.url
    r["redirected"] = page.url.rstrip("/").endswith("/result")
    body = page.inner_text("body")
    r["results_page_text_head"] = body[:200]
    r["shows_100"] = "100%" in body
    r["score_text"] = next(
        (ln for ln in body.splitlines() if ln.strip().endswith("%")), None
    )
    r["table_rows"] = page.locator("table tbody tr").count()
    page.screenshot(path=f"{SHOTS}/{LABEL}_03_results.png", full_page=True)

    # browser BACK to the quiz -> on_load must reset answers
    page.go_back(wait_until="networkidle")
    page.wait_for_timeout(2500)
    r["url_after_back"] = page.url
    checked_after_back = 0
    cbs2 = page.get_by_role("checkbox")
    for i in range(cbs2.count()):
        if cbs2.nth(i).is_checked():
            checked_after_back += 1
    r["checkboxes_checked_after_back"] = checked_after_back
    page.screenshot(path=f"{SHOTS}/{LABEL}_04_back.png", full_page=True)

    # direct load of /result (fresh state -> 0%)
    page.goto(URL + "/result", wait_until="networkidle", timeout=60_000)
    page.wait_for_timeout(2500)
    r["direct_result_title"] = page.title()
    r["direct_result_has_results"] = "Results" in page.inner_text("body")
    page.screenshot(path=f"{SHOTS}/{LABEL}_05_direct_result.png", full_page=True)

    browser.close()

print(json.dumps({
    "label": LABEL, "results": r,
    "console_errors": [c for c in console if c["type"] == "error"],
    "console_warnings": [c for c in console if c["type"] == "warning"],
    "page_errors": page_errors, "failed_requests": failed,
    "bad_responses": sorted(set(bad)),
}, indent=2, default=str))
