"""Playwright driver for the mixed-floor probe app.

Usage: drive_mixed.py <base url> <out dir> <label>
Checks: page loads, lucide svgs (static + dynamic, toggling), shiki + react-syntax-highlighter blocks, moment text,
data_editor canvases (state-backed columns without `type`), add row, form submit (checkbox/switch values, id-only input,
repeated names), window keydown, clipboard paste. Records console errors/warnings, page errors and failed requests.
"""

import json
import os
import sys
import time

assert "/envs/driver/" in sys.executable, sys.executable  # guard: this driver runs in the driver venv
from playwright.sync_api import sync_playwright  # noqa: E402

BASE, OUT, LABEL = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(OUT, exist_ok=True)
res = {"label": LABEL, "checks": [], "console": [], "page_errors": [], "failed_requests": []}


def check(name, ok, detail=""):
    res["checks"].append({"name": name, "ok": bool(ok), "detail": str(detail)[:400]})
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {str(detail)[:200]}")


def wait_text(page, sel, pred, timeout=8.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            t = page.inner_text(sel)
            if pred(t):
                return t
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.2)
    try:
        return page.inner_text(sel)
    except Exception:  # noqa: BLE001
        return None


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = browser.new_context(permissions=["clipboard-read", "clipboard-write"])
    page = ctx.new_page()
    page.on("console", lambda m: res["console"].append({"type": m.type, "text": m.text[:300]}) if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: res["page_errors"].append(str(e)[:300]))
    page.on("requestfailed", lambda r: res["failed_requests"].append(f"{r.url} {r.failure}"))
    page.on("response", lambda r: res["failed_requests"].append(f"{r.url} HTTP {r.status}") if r.status >= 400 else None)
    page.goto(BASE, wait_until="load", timeout=120000)
    t = wait_text(page, "#title", lambda s: "mixed" in s, 30)
    check("page title", t and "mixed" in t, t)
    # wait for websocket hydration: nrows shows 3
    t = wait_text(page, "#nrows", lambda s: s.strip() == "3", 30)
    check("hydrated (nrows=3)", t and t.strip() == "3", t)
    page.screenshot(path=f"{OUT}/{LABEL}-loaded.png", full_page=True)

    # lucide
    n_static = page.locator("#icon_static svg, svg#icon_static").count()
    n_dyn = page.locator("#icon_dynamic svg, svg#icon_dynamic").count()
    cls_static = page.evaluate("() => { const e = document.querySelector('#icon_static'); return e ? e.tagName + ' ' + (e.getAttribute('class')||'') : null }")
    check("lucide static icon rendered as svg", n_static >= 1 or (cls_static and cls_static.startswith("svg")), cls_static)
    cls_dyn = page.evaluate("() => { const e = document.querySelector('#icon_dynamic'); return e ? e.tagName + ' ' + (e.getAttribute('class')||'') : null }")
    check("lucide dynamic icon rendered as svg", n_dyn >= 1 or (cls_dyn and cls_dyn.startswith("svg")), cls_dyn)
    svg_before = page.evaluate("() => { const e = document.querySelector('#icon_dynamic'); return e ? e.innerHTML : null }")
    page.click("#toggle_icon")
    t = wait_text(page, "#icon_name", lambda s: s.strip() == "sun")
    time.sleep(0.5)
    svg_after = page.evaluate("() => { const e = document.querySelector('#icon_dynamic'); return e ? e.innerHTML : null }")
    check("dynamic icon toggles to sun (svg content changes)", t and t.strip() == "sun" and svg_before and svg_after and svg_before != svg_after, f"before={str(svg_before)[:60]} after={str(svg_after)[:60]}")

    # code blocks
    shiki = page.evaluate("() => { const e = document.querySelector('#code_shiki'); return e ? {pre: e.querySelectorAll('pre').length, spans: e.querySelectorAll('span').length, highlighted: e.querySelectorAll('.highlighted, .line.highlighted').length, text: e.innerText.slice(0,80)} : null }")
    check("shiki code block rendered (pre + spans)", shiki and shiki["pre"] >= 1 and shiki["spans"] > 3, shiki)
    check("shiki [!code highlight] transformer applied", shiki and shiki["highlighted"] >= 1, shiki)
    rsh = page.evaluate("() => { const e = document.querySelector('#code_rsh'); return e ? {pre: e.querySelectorAll('pre').length, spans: e.querySelectorAll('span').length, text: e.innerText.slice(0,60)} : null }")
    check("react-syntax-highlighter code block rendered", rsh and rsh["pre"] >= 1 and rsh["spans"] > 3, rsh)

    # moment
    t = wait_text(page, "#moment", lambda s: "2026-10-24 12:30" in s)
    check("moment formats the UTC timestamp", t and "2026-10-24 12:30" in t, t)

    # data editor
    de = page.evaluate("() => ({state: document.querySelectorAll('#de_state canvas').length, literal: document.querySelectorAll('#de_literal canvas').length, state_text: (document.querySelector('#de_state')||{}).innerText})")
    check("data_editor with state-backed columns renders a canvas", de["state"] >= 1, de)
    check("data_editor with literal columns renders a canvas", de["literal"] >= 1, de)
    page.click("#add_row")
    t = wait_text(page, "#nrows", lambda s: s.strip() == "4")
    check("add row -> nrows 4", t and t.strip() == "4", t)
    try:
        box = page.locator("#de_state canvas").first.bounding_box()
        page.mouse.click(box["x"] + 40, box["y"] + 50)
        t = wait_text(page, "#cell", lambda s: s.strip().startswith("["))
        check("on_cell_clicked fired", t and t.strip().startswith("["), t)
    except Exception as e:  # noqa: BLE001
        check("on_cell_clicked fired", False, repr(e))
    page.screenshot(path=f"{OUT}/{LABEL}-de.png", full_page=True)

    # form
    page.fill("#username", "ada")
    page.fill("#idonly", "idval")
    page.click("#agree")
    page.click("#sw")
    page.fill("#tag1", "t1")
    page.fill("#tag2", "t2")
    page.click("#submit")
    t = wait_text(page, "#submit_count", lambda s: s.strip() == "1")
    sub = wait_text(page, "#submitted", lambda s: s.strip().startswith("{"))
    check("form submitted once", t and t.strip() == "1", t)
    try:
        d = json.loads(sub)
    except Exception:  # noqa: BLE001
        d = {}
    res["form_data"] = d
    check("form data has username", d.get("username") == "ada", d)
    check("form data: checkbox value", "agree" in d, f"agree={d.get('agree')!r}")
    check("form data: switch value", "sw" in d, f"sw={d.get('sw')!r}")
    check("form data: id-only input", "idonly" in d, f"idonly={d.get('idonly')!r}")
    check("form data: repeated name tags (dict keeps last)", d.get("tags") == "t2", f"tags={d.get('tags')!r}")
    check("form data: select", d.get("choice") == "a", f"choice={d.get('choice')!r}")

    # window keydown
    page.click("#title")
    page.keyboard.press("F7")
    t = wait_text(page, "#key_count", lambda s: s.strip() != "0")
    lk = page.inner_text("#last_key")
    check("window_event_listener on_key_down fired", t and t.strip() != "0", f"count={t} last_key={lk}")

    # clipboard paste event
    page.evaluate("""() => { const dt = new DataTransfer(); dt.setData('text/plain', 'pasted-text'); const ev = new ClipboardEvent('paste', {clipboardData: dt, bubbles: true}); document.dispatchEvent(ev); }""")
    t = wait_text(page, "#pasted", lambda s: "pasted-text" in s)
    check("clipboard on_paste fired", t and "pasted-text" in t, t)

    page.reload(wait_until="load")
    t = wait_text(page, "#nrows", lambda s: s.strip() in ("3", "4"), 30)
    check("reload hydrates again", t and t.strip() in ("3", "4"), t)
    page.screenshot(path=f"{OUT}/{LABEL}-end.png", full_page=True)
    browser.close()

benign = ("HydrateFallback", "Download the React DevTools", "connecting...", "connected.", "favicon.ico", "[vite]")
res["unexpected_console"] = [c for c in res["console"] if not any(b in c["text"] for b in benign)]
res["failed_requests"] = [f for f in res["failed_requests"] if "favicon" not in f]
with open(f"{OUT}/{LABEL}.json", "w") as f:
    json.dump(res, f, indent=1)
n_ok = sum(c["ok"] for c in res["checks"])
print(f"== {LABEL}: pass={n_ok} fail={len(res['checks']) - n_ok} unexpected_console={len(res['unexpected_console'])} page_errors={len(res['page_errors'])} failed_requests={len(res['failed_requests'])}")
for c in res["unexpected_console"][:12]:
    print("  CONSOLE", c["type"], c["text"][:200])
for e in res["page_errors"][:5]:
    print("  PAGE ERROR", e[:200])
for r in res["failed_requests"][:5]:
    print("  BAD REQ", r[:200])
