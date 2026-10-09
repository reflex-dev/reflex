"""Drive the small reflex-examples apps: counter, traversal, json-tree.

Usage: drive_misc.py <app> <url> <outdir> <tag>
counter    increment/decrement/randomize, reload persistence, colour-mode button.
traversal  7x7 grid (3 walls + red start + green goal), DFS + BFS event chains (each step
           re-queues itself) ending in rx.toast, Clear, slider walls -> Generate Graph,
           reload persistence (deque state var with custom @serializer).
json-tree  dynamic components (state var + computed var holding rx.Component), rx.clipboard
           on_paste with synthetic ClipboardEvent: valid JSON -> nested data_list, invalid
           JSON, second document, reload persistence of the dynamic component state.
"""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from harness import CHROMIUM, Run, guard_driver_python, wait_for  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

guard_driver_python()
APP, URL, OUT, TAG = sys.argv[1:5]
run = Run(TAG, OUT)

CELLS_JS = """() => Array.from(document.querySelectorAll('div')).filter(d => {
  const s = getComputedStyle(d); return s.width === '50px' && s.height === '50px'; })
  .map(d => getComputedStyle(d).backgroundColor)"""
NAMED = {"rgb(0, 0, 255)": "blue", "rgb(255, 0, 0)": "red", "rgb(0, 128, 0)": "green", "rgb(255, 255, 0)": "yellow"}


def cells(page):
    return [NAMED.get(c, "empty") for c in page.evaluate(CELLS_JS)]


def paste(page, text):
    page.evaluate("""(t) => { const dt = new DataTransfer(); dt.setData('text/plain', t);
        document.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true})); }""", text)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM)
    ctx = browser.new_context(viewport={"width": 1200, "height": 1000})
    page = ctx.new_page()
    run.attach(page)
    page.goto(URL, wait_until="load")
    if APP == "counter":
        h = page.locator("h1, .rt-Heading").first
        h.wait_for(timeout=40000)
        wait_for(lambda: page.locator(".rt-Heading").first.inner_text().strip() == "0", 15)
        cnt = lambda: page.locator(".rt-Heading").first.inner_text().strip()  # noqa: E731
        run.check("counter: initial 0", cnt() == "0", cnt())
        for _ in range(3):
            page.get_by_role("button", name="Increment").click()
        ok = wait_for(lambda: cnt() == "3", 5)
        run.check("counter: 3x Increment -> 3", bool(ok), cnt())
        page.get_by_role("button", name="Decrement").click()
        ok = wait_for(lambda: cnt() == "2", 5)
        run.check("counter: Decrement -> 2", bool(ok), cnt())
        page.get_by_role("button", name="Randomize").click()
        time.sleep(1)
        v = cnt()
        run.check("counter: Randomize -> 0..100", v.isdigit() and 0 <= int(v) <= 100, v)
        run.shot(page, "01_counter")
        page.reload(wait_until="load")
        ok = wait_for(lambda: cnt() == v, 15)
        run.check("counter: value survives reload (same tab token)", bool(ok), f"{cnt()} vs {v}")
        before = page.evaluate("() => document.documentElement.className")
        page.locator("button:has(svg.lucide-sun), button:has(svg.lucide-moon)").first.click()
        ok = wait_for(lambda: page.evaluate("() => document.documentElement.className") != before, 5)
        run.check("counter: colour-mode button flips theme", bool(ok),
                  f"{before} -> {page.evaluate('() => document.documentElement.className')}")
        run.shot(page, "02_counter_dark")
    elif APP == "traversal":
        page.get_by_role("heading", name="Graph Traversal").wait_for(timeout=40000)
        c = wait_for(lambda: (lambda x: x if len(x) == 49 else None)(cells(page)), 15)
        run.check("traversal: 7x7 grid", bool(c), f"n={len(cells(page))}")
        c = cells(page)
        run.check("traversal: 3 walls + red + green", c.count("blue") == 3 and c.count("red") == 1 and c.count("green") == 1,
                  {k: c.count(k) for k in set(c)})
        run.shot(page, "01_grid")
        for algo in ("DFS", "BFS"):
            page.get_by_role("combobox").first.click()
            page.get_by_role("option", name=algo).click()
            time.sleep(0.3)
            page.get_by_role("button", name="Run").click()
            t0 = time.time()
            ok = wait_for(lambda: page.locator("[data-sonner-toast]").count() > 0, 20, 0.1)
            msg = page.locator("[data-sonner-toast]").last.inner_text() if ok else ""
            dur = round(time.time() - t0, 2)
            yel = cells(page).count("yellow")
            run.check(f"traversal: {algo} event chain completes with toast", bool(ok) and bool(re.search(r"Path found|No path", msg)),
                      f"toast={msg!r} yellow={yel} t={dur}s")
            run.notes[f"{algo}_duration_s"] = dur
            run.notes[f"{algo}_yellow"] = yel
            run.check(f"traversal: {algo} coloured visited cells", yel > 0, yel)
            run.shot(page, f"02_{algo}")
            page.get_by_role("button", name="Clear").click()
            ok = wait_for(lambda: cells(page).count("yellow") == 0, 5)
            run.check(f"traversal: Clear after {algo} resets visited cells", bool(ok))
            page.wait_for_timeout(4500)  # let toasts expire
        thumb = page.get_by_role("slider").first
        thumb.focus()
        for _ in range(2):
            page.keyboard.press("ArrowRight")
            time.sleep(0.3)
        ok = wait_for(lambda: page.get_by_text("5 walls").count() > 0, 5)
        run.check("traversal: slider -> 5 walls (set_walls)", bool(ok), page.locator("text=/walls/").first.inner_text())
        page.get_by_role("button", name="Generate Graph").click()
        ok = wait_for(lambda: cells(page).count("blue") == 5, 5)
        run.check("traversal: Generate Graph with 5 walls", bool(ok), {k: cells(page).count(k) for k in set(cells(page))})
        grid_before = cells(page)
        page.reload(wait_until="load")
        page.get_by_role("heading", name="Graph Traversal").wait_for(timeout=30000)
        ok = wait_for(lambda: cells(page) == grid_before and page.get_by_text("5 walls").count() > 0, 15)
        run.check("traversal: graph + walls survive reload", bool(ok))
        run.shot(page, "03_after_reload")
    elif APP == "json-tree":
        page.get_by_text("Paste JSON data").wait_for(timeout=40000)
        run.check("json-tree: initial dynamic components (info + 'No JSON data')",
                  page.get_by_text("No JSON data").count() == 1)
        doc = {"name": "upgrade", "versions": ["0.9.12", "0.10.0a1"], "nested": {"ok": True, "n": 3, "deep": {"x": [1, {"y": "z"}]}}}
        raw = json.dumps(doc)
        paste(page, raw)
        ok = wait_for(lambda: page.get_by_text(f"Loaded {len(raw)} bytes of JSON data.").count() == 1, 10)
        run.check("json-tree: paste valid JSON -> info updated", bool(ok))
        ok = wait_for(lambda: page.locator(".rt-DataListLabel").count() >= 6, 10)
        labels = page.locator(".rt-DataListLabel").all_inner_texts()
        items = page.locator("li").all_inner_texts()
        run.check("json-tree: nested data_list + list items rendered from computed var",
                  bool(ok) and {"name", "versions", "nested", "ok", "n", "deep", "x", "y"} <= set(labels) and len(items) >= 4,
                  f"labels={labels} li={len(items)}")
        run.shot(page, "01_tree")
        paste(page, "{not json")
        time.sleep(1.5)
        run.check("json-tree: invalid JSON -> tree cleared ('No JSON data')", page.get_by_text("No JSON data").count() == 1)
        run.notes["after_invalid_body"] = page.inner_text("body")[:300]
        raw2 = json.dumps([{"k": i} for i in range(3)])
        paste(page, raw2)
        ok = wait_for(lambda: page.get_by_text(f"Loaded {len(raw2)} bytes of JSON data.").count() == 1, 10)
        run.check("json-tree: second paste (list of dicts) renders", bool(ok) and page.locator(".rt-DataListLabel").count() == 3,
                  page.locator(".rt-DataListLabel").all_inner_texts())
        page.reload(wait_until="load")
        ok = wait_for(lambda: page.get_by_text(f"Loaded {len(raw2)} bytes of JSON data.").count() == 1 and
                      page.locator(".rt-DataListLabel").count() == 3, 15)
        run.check("json-tree: dynamic component state survives reload (hydration)", bool(ok), page.inner_text("body")[:200])
        run.shot(page, "02_after_reload")
    browser.close()
sys.exit(run.finish())
