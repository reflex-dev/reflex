"""Drive the reflex-examples `quiz` app (rx.code_block, radios, checkboxes, on_load reset, rx.redirect, 2 pages).

Usage: drive_quiz.py <url> <outdir> <tag>
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from harness import CHROMIUM, Run, guard_driver_python  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

guard_driver_python()
URL, OUT, TAG = sys.argv[1:4]
URL = URL.rstrip("/")
run = Run(TAG, OUT)


def pump(page, cond, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if cond():
                return True
        except Exception:  # noqa: BLE001
            pass
        page.wait_for_timeout(200)
    return bool(cond())


def path(page):
    return page.evaluate("() => location.pathname")


def answer(page, q1, q2, q3_idx):
    page.get_by_role("radio", name=q1, exact=True).first.click()
    page.wait_for_timeout(250)
    page.get_by_role("radio", name=q2, exact=True).first.click()
    page.wait_for_timeout(250)
    cbs = page.get_by_role("checkbox")
    for i in q3_idx:
        cbs.nth(i).click()
        page.wait_for_timeout(200)
    page.wait_for_timeout(600)


def results(page):
    rows = page.locator("table tbody tr")
    out = []
    for i in range(rows.count()):
        cells = rows.nth(i).locator("td")
        icon = rows.nth(i).locator("svg").first.get_attribute("class") if rows.nth(i).locator("svg").count() else None
        out.append([cells.nth(0).inner_text().strip(), (icon or "").replace("lucide ", ""), cells.nth(2).inner_text().strip(), cells.nth(3).inner_text().strip()])
    return out


def score(page):
    h = page.locator("h1,h2,h3,h4").filter(has_text="%")
    return h.first.inner_text().strip() if h.count() else None


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM)
    ctx = browser.new_context(viewport={"width": 1280, "height": 1000}, color_scheme="light")
    page = ctx.new_page()
    run.attach(page, "main")
    page.goto(URL + "/", wait_until="load")
    page.get_by_role("button", name="Submit").wait_for(timeout=60000)
    pump(page, lambda: page.locator("pre").count() > 0, 15)
    page.wait_for_timeout(1000)
    cb = page.evaluate("""() => { const pre = document.querySelector('pre'); if (!pre) return null;
        return {text: pre.innerText, cls: pre.className, spans: pre.querySelectorAll('span').length,
                colored: [...pre.querySelectorAll('span')].filter(s => s.style.color || getComputedStyle(s).color !== getComputedStyle(pre).color).length}; }""")
    run.notes["code_block"] = cb
    run.check("title + rx.code_block renders the snippet with syntax-highlight spans", page.title() == "Quiz - Reflex" and cb and "b += [30, 40]" in cb["text"] and cb["colored"] > 3,
              f"title={page.title()} spans={cb and cb['spans']} colored={cb and cb['colored']} cls={cb and cb['cls'][:80]}")
    run.check("questions render (4 radios, 5 checkboxes)", page.get_by_role("radio").count() == 4 and page.get_by_role("checkbox").count() == 5,
              f"radios={page.get_by_role('radio').count()} checkboxes={page.get_by_role('checkbox').count()}")
    run.shot(page, "01_quiz")
    answer(page, "False", "[10, 20, 30, 40]", (2, 3, 4))
    page.get_by_role("button", name="Submit").click()
    ok = pump(page, lambda: path(page).rstrip("/") == "/result" and score(page) is not None, 15)
    page.wait_for_timeout(800)
    res = results(page)
    run.notes["results_all_correct"] = res
    run.check("all correct -> redirect /result shows 100% and 3 check rows", ok and score(page) == "100%" and len(res) == 3 and all("check" in r[1] for r in res),
              f"path={path(page)} score={score(page)} rows={res}")
    run.check("answers rendered via Var.to_string()", [r[2] for r in res] == ['"False"', '"[10, 20, 30, 40]"', "[false,false,true,true,true]"], [r[2] for r in res])
    run.shot(page, "02_result_100")
    page.reload(wait_until="load")
    pump(page, lambda: score(page) == "100%", 15)
    run.check("reload /result keeps the score (state per token)", score(page) == "100%", score(page))
    page.get_by_role("link", name="Take Quiz Again").click() if page.get_by_role("link", name="Take Quiz Again").count() else page.get_by_role("button", name="Take Quiz Again").click()
    ok = pump(page, lambda: path(page) == "/" and page.get_by_role("checkbox").count() == 5, 15)
    page.wait_for_timeout(800)
    checked = sum(1 for i in range(5) if page.get_by_role("checkbox").nth(i).get_attribute("data-state") == "checked")
    run.check("Take Quiz Again -> / (client nav), checkboxes start unchecked", ok and checked == 0, f"path={path(page)} checked={checked}")
    answer(page, "True", "[10, 20, 30, 40]", (2, 3, 4))
    page.get_by_role("button", name="Submit").click()
    ok = pump(page, lambda: path(page).rstrip("/") == "/result" and score(page) is not None, 15)
    page.wait_for_timeout(800)
    res2 = results(page)
    run.notes["results_one_wrong"] = res2
    run.check("one wrong answer -> 66% and an x icon on row 1", ok and score(page) == "66%" and "x" in res2[0][1] and "check" in res2[1][1],
              f"score={score(page)} rows={res2}")
    page.go_back(wait_until="load")
    ok = pump(page, lambda: path(page) == "/" and page.get_by_role("checkbox").count() == 5, 15)
    page.wait_for_timeout(1000)
    checked = sum(1 for i in range(5) if page.get_by_role("checkbox").nth(i).get_attribute("data-state") == "checked")
    run.notes["checked_after_back"] = checked
    run.check("browser back -> / again (on_load reset answers server-side)", ok, f"path={path(page)} checked_checkboxes_dom={checked}")
    page.get_by_role("button", name="Submit").click()
    ok = pump(page, lambda: path(page).rstrip("/") == "/result" and score(page) is not None, 15)
    page.wait_for_timeout(600)
    run.notes["results_after_back_submit"] = [score(page), results(page)]
    run.check("submit right after back: on_load reset -> 0%", ok and score(page) == "0%", f"score={score(page)} rows={results(page)}")
    # color mode toggle on the results page
    theme = lambda: page.evaluate("() => [document.documentElement.className, getComputedStyle(document.querySelector('.radix-themes')).backgroundColor]")  # noqa: E731
    t0 = theme()
    page.locator("button.rt-IconButton").first.click()
    ok = pump(page, lambda: theme() != t0, 5)
    run.check("color mode button toggles theme (html class + radix-themes background)", ok and "dark" in theme()[0], f"{t0} -> {theme()}")
    run.shot(page, "03_result_dark")
    # direct /result in a fresh session
    ctx2 = browser.new_context(viewport={"width": 1280, "height": 1000}, color_scheme="light")
    p2 = ctx2.new_page()
    run.attach(p2, "fresh")
    p2.goto(URL + "/result", wait_until="load")
    ok = pump(p2, lambda: score(p2) is not None, 15)
    p2.wait_for_timeout(800)
    run.check("direct /result in a fresh session renders 0% and an empty table", ok and score(p2) == "0%" and results(p2) == [] and p2.title() == "Quiz Results",
              f"score={score(p2)} rows={results(p2)} title={p2.title()}")
    run.shot(p2, "04_direct_result")
    browser.close()
sys.exit(run.finish())
