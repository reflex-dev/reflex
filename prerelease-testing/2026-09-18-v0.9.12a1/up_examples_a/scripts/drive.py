"""Drive the up_examples_a reflex-examples apps in Chromium and report anomalies.

Usage:
  NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
    $SB/envs/driver/bin/python drive.py <app> <base_url> <tag> <outdir>

<app> is one of counter todo clock upload lorem-stream snakegame.
Captures console messages, page errors, failed requests, >=400 responses and
screenshots; writes <outdir>/<app>-<tag>.json and PNGs.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

CHROMIUM = "/opt/pw-browsers/chromium"
BENIGN = [
    re.compile(r"Hey developer.*HydrateFallback|reactrouter\.com/start/framework/route-module"),
    re.compile(r"\[vite\] (connecting|connected)"),
    re.compile(r"Download the React DevTools"),
]


def benign(t: str) -> bool:
    return any(p.search(t) for p in BENIGN)


def flow_counter(page, shot, rec):
    page.wait_for_selector("text=Increment", timeout=30000)
    shot("load")
    def heading():
        return page.locator("h1,h2,h3").first.inner_text().strip()
    rec["initial_count"] = heading()
    for _ in range(3):
        page.click("text=Increment")
        page.wait_for_timeout(200)
    rec["after_3_inc"] = heading()
    page.click("text=Decrement")
    page.wait_for_timeout(300)
    rec["after_dec"] = heading()
    page.click("text=Randomize")
    page.wait_for_timeout(400)
    rec["after_random"] = heading()
    shot("interacted")
    # reload -> state should reset to 0 per new token? (token is stored in localStorage)
    page.reload()
    page.wait_for_selector("text=Increment", timeout=30000)
    page.wait_for_timeout(800)
    rec["after_reload"] = heading()
    # color mode button (client-side only)
    page.click("button:below(:text('Increment'))" if False else ".rt-IconButton, button >> nth=0")
    page.wait_for_timeout(300)
    shot("after_reload")


def flow_todo(page, shot, rec):
    page.wait_for_selector("input[name=new_item]", timeout=30000)
    shot("load")
    rec["initial_items"] = page.locator("li").all_inner_texts()
    for item in ["buy milk", "walk dog", "ship 0.9.12"]:
        page.fill("input[name=new_item]", item)
        page.press("input[name=new_item]", "Enter")
        page.wait_for_timeout(400)
    rec["after_add"] = page.locator("li").all_inner_texts()
    shot("added")
    # complete (delete) the first item via its check icon button
    page.locator("li button").first.click()
    page.wait_for_timeout(500)
    rec["after_finish_first"] = page.locator("li").all_inner_texts()
    page.reload()
    page.wait_for_selector("input[name=new_item]", timeout=30000)
    page.wait_for_timeout(1000)
    rec["after_reload"] = page.locator("li").all_inner_texts()
    shot("after_reload")


def flow_clock(page, shot, rec):
    page.wait_for_selector("button[role=combobox]", timeout=30000)
    page.wait_for_timeout(1000)
    shot("load")
    def digital():
        return " ".join(page.locator("div:has(> h1), div").nth(0).inner_text().split())[:80]
    rec["zone_initial"] = page.locator("button[role=combobox]").inner_text().strip()
    # start the clock
    page.locator("button[role=switch]").click()
    page.wait_for_timeout(300)
    t0 = page.locator("h1").all_inner_texts()
    page.wait_for_timeout(2500)
    t1 = page.locator("h1").all_inner_texts()
    rec["ticking_t0"] = t0
    rec["ticking_t1"] = t1
    rec["ticked"] = t0 != t1
    shot("running")
    # change timezone while running
    page.locator("button[role=combobox]").click()
    page.wait_for_timeout(400)
    page.locator("div[role=option]:has-text('Europe/Paris')").first.click()
    page.wait_for_timeout(1200)
    rec["zone_after"] = page.locator("button[role=combobox]").inner_text().strip()
    rec["time_after_zone"] = page.locator("h1").all_inner_texts()
    shot("paris")
    # stop
    page.locator("button[role=switch]").click()
    page.wait_for_timeout(300)
    s0 = page.locator("h1").all_inner_texts()
    page.wait_for_timeout(2500)
    s1 = page.locator("h1").all_inner_texts()
    rec["stopped_no_tick"] = s0 == s1
    # reload: cookie should persist zone, on_load stops clock
    page.reload()
    page.wait_for_selector("button[role=combobox]", timeout=30000)
    page.wait_for_timeout(1500)
    rec["zone_after_reload"] = page.locator("button[role=combobox]").inner_text().strip()
    rec["switch_after_reload_checked"] = page.locator("button[role=switch]").get_attribute("data-state")
    shot("after_reload")


def flow_upload(page, shot, rec, outdir):
    page.wait_for_selector("text=Select File(s)", timeout=30000)
    shot("load")
    d = Path(outdir) / "uploadfiles"
    d.mkdir(parents=True, exist_ok=True)
    f1 = d / "alpha.txt"
    f2 = d / "beta.txt"
    f1.write_text("alpha contents 0.9.12a1\n" * 3)
    f2.write_text("beta contents\n" * 5)
    page.set_input_files("input[type=file]", [str(f1), str(f2)])
    page.wait_for_timeout(600)
    rec["selected_files_text"] = page.locator("text=alpha.txt").count()
    shot("selected")
    page.click("button:has-text('Upload')")
    page.wait_for_timeout(2500)
    rec["links"] = page.locator("a").all_inner_texts()
    rec["progress_value"] = page.locator("[role=progressbar], .rt-ProgressRoot").first.get_attribute("data-value")
    shot("uploaded")
    # clear selection then verify the list survives a reload
    page.reload()
    page.wait_for_selector("text=Select File(s)", timeout=30000)
    page.wait_for_timeout(1200)
    rec["links_after_reload"] = page.locator("a").all_inner_texts()
    # fetch one uploaded file through the backend to verify serving
    hrefs = page.locator("a").evaluate_all("els => els.map(e => e.getAttribute('href'))")
    rec["hrefs"] = hrefs
    if hrefs:
        r = page.request.get(hrefs[0] if hrefs[0].startswith("http") else page.url.rstrip("/") + hrefs[0])
        rec["fetch_status"] = r.status
        rec["fetch_body"] = r.text()[:60]
    shot("after_reload")


def flow_lorem(page, shot, rec):
    page.wait_for_selector("text=New Task", timeout=30000)
    shot("load")
    for _ in range(3):
        page.click("text=New Task")
        page.wait_for_timeout(500)
    page.wait_for_timeout(2500)
    texts = page.locator("div.rt-Flex > div").all_inner_texts()
    rec["n_tasks"] = page.locator("button:has-text('❌')").count()
    rec["streamed_len_after_3s"] = [len(t) for t in texts]
    shot("streaming")
    # stop one stream with the toggle button
    page.locator("button:has-text('⏯️')").first.click()
    page.wait_for_timeout(1500)
    rec["n_tasks_after_toggle"] = page.locator("button:has-text('❌')").count()
    # kill one task
    page.locator("button:has-text('❌')").first.click()
    page.wait_for_timeout(800)
    rec["n_tasks_after_kill"] = page.locator("button:has-text('❌')").count()
    shot("after_kill")
    # navigate away and back (client-side) while streams run
    page.click("text=New Task")
    page.wait_for_timeout(600)
    before = page.locator("button:has-text('❌')").count()
    page.goto(page.url.rstrip("/") + "/?nav=1")
    page.wait_for_timeout(2500)
    rec["n_tasks_before_nav"] = before
    rec["n_tasks_after_nav"] = page.locator("button:has-text('❌')").count()
    texts2 = page.locator("div.rt-Flex > div").all_inner_texts()
    rec["streamed_len_after_nav"] = [len(t) for t in texts2]
    shot("after_nav")


def flow_snake(page, shot, rec):
    page.wait_for_selector("text=PAUSE", timeout=30000)
    page.wait_for_timeout(800)
    shot("load")
    def score():
        return page.locator("text=SCORE").first.evaluate("e => e.parentElement.innerText")
    rec["score_initial"] = score()
    page.click("text=RUN")
    page.wait_for_timeout(1200)
    body = page.locator("body")
    for key in ["ArrowUp", "ArrowLeft", "ArrowDown", "ArrowRight", "k", "h"]:
        body.press(key)
        page.wait_for_timeout(350)
    page.wait_for_timeout(1500)
    rec["score_after_moves"] = score()
    cells = page.locator("div.rt-Grid > div").count()
    rec["grid_cells"] = cells
    shot("playing")
    page.click("text=PAUSE")
    page.wait_for_timeout(800)
    c0 = page.locator("div.rt-Grid").first.inner_html()[:2000]
    page.wait_for_timeout(2000)
    c1 = page.locator("div.rt-Grid").first.inner_html()[:2000]
    rec["paused_board_static"] = c0 == c1
    rec["switch_state_paused"] = page.locator("button[role=switch]").get_attribute("data-state")
    # Escape key toggles running via GlobalKeyWatcher
    body.press("Escape")
    page.wait_for_timeout(1000)
    rec["switch_state_after_escape"] = page.locator("button[role=switch]").get_attribute("data-state")
    page.wait_for_timeout(1500)
    rec["score_after_escape"] = score()
    shot("after_escape")
    page.reload()
    page.wait_for_selector("text=PAUSE", timeout=30000)
    page.wait_for_timeout(1200)
    rec["score_after_reload"] = score()
    shot("after_reload")


def main() -> int:
    app, url, tag, outdir = sys.argv[1:5]
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    console, errors, failed, bad = [], [], [], []
    rec: dict = {"app": app, "url": url, "tag": tag}
    shots = []

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        ctx = browser.new_context(viewport={"width": 1280, "height": 1000})
        page = ctx.new_page()
        page.on("console", lambda m: console.append(f"[{m.type}] {m.text}"))
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("requestfailed", lambda r: failed.append(f"{r.method} {r.url} :: {r.failure}"))
        page.on("response", lambda r: bad.append(f"{r.status} {r.request.method} {r.url}") if r.status >= 400 else None)

        def shot(name):
            path = out / f"{app}-{tag}-{name}.png"
            try:
                page.screenshot(path=str(path))
                shots.append(str(path))
            except Exception as e:
                rec.setdefault("shot_errors", []).append(f"{name}: {e}")

        t0 = time.time()
        try:
            page.goto(url, timeout=90000)
            rec["load_seconds"] = round(time.time() - t0, 2)
            if app == "counter":
                flow_counter(page, shot, rec)
            elif app == "todo":
                flow_todo(page, shot, rec)
            elif app == "clock":
                flow_clock(page, shot, rec)
            elif app == "upload":
                flow_upload(page, shot, rec, outdir)
            elif app == "lorem-stream":
                flow_lorem(page, shot, rec)
            elif app == "snakegame":
                flow_snake(page, shot, rec)
            else:
                raise SystemExit(f"unknown app {app}")
            rec["flow_ok"] = True
        except Exception as e:
            rec["flow_ok"] = False
            rec["flow_error"] = f"{type(e).__name__}: {e}"
            shot("failure")
        finally:
            ctx.close()
            browser.close()

    rec["console_all"] = console
    rec["console_notable"] = [c for c in console if not benign(c) and not c.startswith("[log]")]
    rec["console_errors"] = [c for c in console if c.startswith("[error]") and not benign(c)]
    rec["page_errors"] = errors
    rec["failed_requests"] = failed
    rec["bad_responses"] = bad
    rec["screenshots"] = shots
    (out / f"{app}-{tag}.json").write_text(json.dumps(rec, indent=2, default=str))
    print(json.dumps({k: v for k, v in rec.items() if k != "console_all"}, indent=2, default=str))
    ok = rec.get("flow_ok") and not rec["console_errors"] and not errors and not rec["bad_responses"]
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
