"""Drive a reflex-examples app and capture everything an upgrade could break.

Usage: python drive_up.py <app-slug> <frontend_port> <out.json>
"""

import json
import sys

from playwright.sync_api import sync_playwright

APP, PORT, OUT = sys.argv[1], int(sys.argv[2]), sys.argv[3]
BASE = f"http://localhost:{PORT}"
R = {"app": APP, "steps": [], "console": [], "pageerrors": [], "failed": [], "http_errors": []}


def step(n, **kw):
    """Record a step."""
    R["steps"].append({"step": n, **kw})
    print(f"[{n}] " + json.dumps(kw, default=str)[:500], flush=True)


def counts(page):
    """Structural fingerprint of the rendered page."""
    return page.evaluate("""() => ({
        svg: document.querySelectorAll('svg').length,
        buttons: document.querySelectorAll('button').length,
        rows: document.querySelectorAll('tbody tr').length,
        inputs: document.querySelectorAll('input').length,
        recharts: document.querySelectorAll('.recharts-wrapper').length,
        plotly: document.querySelectorAll('.js-plotly-plot').length,
        text_len: document.body.innerText.length,
    })""")


with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
    page = br.new_context().new_page()
    page.on("console", lambda m: R["console"].append({"type": m.type, "text": m.text[:300]}))
    page.on("pageerror", lambda e: R["pageerrors"].append(str(e)[:300]))
    page.on("requestfailed", lambda r: R["failed"].append({"url": r.url[:160], "err": str(r.failure)[:120]}))
    page.on("response", lambda r: R["http_errors"].append({"url": r.url[:160], "status": r.status})
            if r.status >= 400 else None)

    page.goto(BASE, wait_until="networkidle")
    page.wait_for_timeout(3000)
    step("load", counts=counts(page), head=page.locator("body").inner_text()[:200])

    if APP == "local_component":
        step("greeting_initial", greeting=page.locator("#greeting").inner_text(),
             bg=page.locator("#greeting").evaluate("e => getComputedStyle(e).backgroundColor"))
        page.locator("#greeting").click()
        page.wait_for_timeout(900)
        step("popover_open", inputs=page.locator("input").count())
        page.locator("input[name='who']").fill("reflex-qa")
        page.wait_for_timeout(600)
        step("typed", greeting=page.locator("#greeting").inner_text())
        page.locator("input[name='who']").press("Enter")
        page.wait_for_timeout(1200)
        step("submitted", greeting=page.locator("#greeting").inner_text())
        page.locator("#greeting").click(button="right")
        page.wait_for_timeout(700)
        step("right_click_console",
             console_logs=[c["text"] for c in R["console"] if "pass events" in c["text"]])
        page.get_by_text("Scroll to Greeting").click()
        page.wait_for_timeout(1200)
        step("scrolled", y=page.evaluate("() => Math.round(window.scrollY)"))

    elif APP == "lorem_stream":
        page.get_by_text("New Task").click()
        page.wait_for_timeout(3500)
        t1 = page.locator("body").inner_text()
        step("task1_streaming", len=len(t1), counts=counts(page))
        page.wait_for_timeout(3500)
        t2 = page.locator("body").inner_text()
        step("task1_grew", grew=len(t2) > len(t1), len=len(t2))
        page.get_by_text("New Task").click()
        page.wait_for_timeout(3000)
        step("task2", counts=counts(page), tasks=page.locator("button:has-text('❌')").count())
        page.locator("button:has-text('⏯️')").first.click()
        page.wait_for_timeout(2500)
        t3 = page.locator("body").inner_text()
        page.wait_for_timeout(2500)
        step("after_pause", frozen=page.locator("body").inner_text() == t3)
        page.locator("button:has-text('❌')").first.click()
        page.wait_for_timeout(1500)
        step("after_kill", tasks=page.locator("button:has-text('❌')").count())

    elif APP == "data_visualisation":
        page.wait_for_timeout(4000)
        step("table", counts=counts(page))
        heads = page.locator("thead th").all_inner_texts()
        step("columns", columns=heads[:12])
        first_row = page.locator("tbody tr").first.inner_text() if page.locator("tbody tr").count() else "<none>"
        step("first_row", row=first_row[:200])
        # sort control
        sel = page.locator("select, [role='combobox']")
        step("controls", selects=sel.count(), buttons=page.locator("button").count())
        if sel.count():
            try:
                sel.first.click()
                page.wait_for_timeout(900)
                step("sort_opened", body=page.locator("body").inner_text()[:160])
                page.keyboard.press("Escape")
            except Exception as e:  # noqa: BLE001
                step("sort_failed", err=f"{type(e).__name__}: {e}")
        page.wait_for_timeout(800)
        step("final", counts=counts(page))

    R["console_errors"] = [c for c in R["console"] if c["type"] == "error"]
    br.close()

with open(OUT, "w") as f:
    json.dump(R, f, indent=1)
print("\nCONSOLE ERRORS:", json.dumps(R["console_errors"])[:900])
print("PAGE ERRORS:", json.dumps(R["pageerrors"])[:600])
print("FAILED:", json.dumps(R["failed"])[:400])
print("HTTP>=400:", json.dumps(R["http_errors"])[:600])
print("saved", OUT)
