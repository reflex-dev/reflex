"""Drive the renderapp probe app and collect render counts, ws frames, console.

Usage: python drive_render.py <frontend_url> <outdir> <label>
"""

import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
OUT = Path(sys.argv[2])
LABEL = sys.argv[3]
OUT.mkdir(parents=True, exist_ok=True)

result = {"label": LABEL, "base": BASE, "marks": {}, "events": [], "notes": []}
console = []
page_errors = []
failed = []
bad_responses = []
ws_frames = []

INIT = """
window.__renders = window.__renders || {};
window.__longtasks = [];
try {
  new PerformanceObserver((l) => {
    for (const e of l.getEntries()) window.__longtasks.push(Math.round(e.duration));
  }).observe({entryTypes: ['longtask']});
} catch (e) {}
"""


def snap(page, name):
    r = page.evaluate("() => JSON.parse(JSON.stringify(window.__renders || {}))")
    result["marks"][name] = r
    return r


def diff(a, b):
    keys = sorted(set(a) | set(b))
    return {k: b.get(k, 0) - a.get(k, 0) for k in keys}


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = browser.new_context()
    ctx.add_init_script(INIT)
    page = ctx.new_page()
    page.on("console", lambda m: console.append({"type": m.type, "text": m.text[:600]}))
    page.on("pageerror", lambda e: page_errors.append(str(e)[:800]))
    page.on("requestfailed", lambda r: failed.append({"url": r.url, "err": str(r.failure)}))
    page.on(
        "response",
        lambda r: bad_responses.append({"url": r.url, "status": r.status})
        if r.status >= 400
        else None,
    )
    page.on(
        "websocket",
        lambda ws: (
            ws.on("framereceived", lambda f: ws_frames.append(("recv", time.time(), f if isinstance(f, str) else "<bin>"))),
            ws.on("framesent", lambda f: ws_frames.append(("sent", time.time(), f if isinstance(f, str) else "<bin>"))),
        ),
    )

    t0 = time.time()
    page.goto(BASE + "/", wait_until="load")
    # wait for hydrate + on_load (A=1, B=1)
    page.wait_for_selector("#dual-value", timeout=60000)
    page.wait_for_function(
        "() => document.querySelector('#dual-value') && document.querySelector('#dual-value').textContent === '1/1'",
        timeout=60000,
    )
    result["load_seconds"] = round(time.time() - t0, 2)
    time.sleep(1.0)
    m0 = snap(page, "after_load_onload")
    result["onload_ws_frames"] = [f[2][:900] for f in ws_frames if f[0] == "recv"]

    # count deltas received during initial load carrying both substates
    both = 0
    delta_frames = 0
    for kind, _ts, f in ws_frames:
        if kind != "recv" or not f.startswith("42"):
            continue
        delta_frames += 1
        if '"SubA"' in f or "sub_a" in f:
            pass
        if re.search(r"renderapp___renderapp____sub_a", f) and re.search(
            r"renderapp___renderapp____sub_b", f
        ):
            both += 1
    result["initial_recv_event_frames"] = delta_frames
    result["initial_frames_with_both_substates"] = both

    # --- M1: bump A x5
    before = snap(page, "pre_bumpA")
    for _ in range(5):
        page.click("#a-btn")
    page.wait_for_function(
        "() => document.querySelector('[data-value=\"A\"]').textContent === '6'", timeout=20000
    )
    time.sleep(0.6)
    after = snap(page, "post_bumpA")
    result["events"].append({"name": "bumpA_x5", "delta": diff(before, after)})

    # --- M2: bump C x5
    before = snap(page, "pre_bumpC")
    for _ in range(5):
        page.click("#c-btn")
    page.wait_for_function(
        "() => document.querySelector('[data-value=\"C\"]').textContent === '5'", timeout=20000
    )
    time.sleep(0.6)
    after = snap(page, "post_bumpC")
    result["events"].append({"name": "bumpC_x5", "delta": diff(before, after)})

    # --- M3: event chain H -> C -> A
    before = snap(page, "pre_chain")
    page.click("#h-btn")
    page.wait_for_function(
        "() => document.querySelector('[data-value=\"H\"]').textContent === '1'", timeout=20000
    )
    time.sleep(0.6)
    after = snap(page, "post_chain")
    result["events"].append({"name": "chain_H_C_A", "delta": diff(before, after)})

    # --- M4: ComponentState
    before = snap(page, "pre_cs")
    page.click("#cs-btn")
    page.click("#cs-btn")
    page.click("#cs2-btn")
    time.sleep(1.0)
    after = snap(page, "post_cs")
    result["cs_values"] = [
        page.inner_text("#cs-value"),
        page.inner_text("#cs2-value"),
    ]
    result["events"].append({"name": "componentstate_clicks", "delta": diff(before, after)})

    # --- M5: background storm on B while clicking A
    page.evaluate("() => { window.__longtasks = []; }")
    before = snap(page, "pre_storm")
    tstorm = time.time()
    page.click("#storm-btn")
    for _ in range(10):
        page.click("#a-btn")
        time.sleep(0.45)
    time.sleep(1.0)
    after = snap(page, "post_storm")
    result["storm_seconds"] = round(time.time() - tstorm, 2)
    result["events"].append({"name": "storm_B_5s_plus_10_A_clicks", "delta": diff(before, after)})
    result["longtasks_during_storm"] = page.evaluate("() => window.__longtasks")
    result["storm_values"] = {
        "A": page.inner_text('[data-value="A"]'),
        "B": page.inner_text('[data-value="B"]'),
    }
    page.screenshot(path=str(OUT / f"{LABEL}_after_storm.png"))

    # --- M6: color mode toggles
    before = snap(page, "pre_colormode")
    modes = []
    for _ in range(4):
        page.click("button.rt-BaseButton, .rx-color-mode-button" if False else "#root button:has-text('')" if False else "#root")
        break
    # click the actual color mode button (it is the only button without an id inside color_section)
    cm_button = page.locator("#root button:not([id])").first
    for _ in range(4):
        cm_button.click()
        time.sleep(0.35)
        modes.append(page.inner_text("#cm-text"))
    time.sleep(0.5)
    after = snap(page, "post_colormode")
    result["colormode_sequence"] = modes
    result["events"].append({"name": "colormode_toggle_x4", "delta": diff(before, after)})
    page.screenshot(path=str(OUT / f"{LABEL}_colormode.png"))

    # --- M6b: system preference emulation
    page.emulate_media(color_scheme="dark")
    time.sleep(0.5)
    result["cm_after_emulate_dark"] = page.inner_text("#cm-text")
    page.emulate_media(color_scheme="light")
    time.sleep(0.5)
    result["cm_after_emulate_light"] = page.inner_text("#cm-text")
    page.emulate_media(color_scheme="no-preference")

    # --- M7: client storage + client_state
    page.fill("#ls-input", "LSVAL")
    page.fill("#ss-input", "SSVAL")
    page.fill("#ck-input", "CKVAL")
    page.fill("#cs-input", "CSVAL")
    time.sleep(1.2)
    result["storage_before_reload"] = {
        "ls": page.input_value("#ls-input"),
        "ss": page.input_value("#ss-input"),
        "ck": page.input_value("#ck-input"),
        "cs": page.input_value("#cs-input"),
        "ls_echo": page.inner_text("#ls-echo"),
        "ck_echo": page.inner_text("#ck-echo"),
    }

    # --- M8: late-mounted component
    before = snap(page, "pre_late")
    page.click("#late-toggle")
    page.wait_for_selector("#late-btn", timeout=20000)
    page.click("#late-btn")
    time.sleep(0.8)
    result["late_value"] = page.inner_text("#late-value")
    after = snap(page, "post_late")
    result["events"].append({"name": "late_mount_and_bump", "delta": diff(before, after)})

    # --- M9: navigation to page2 and back
    before = snap(page, "pre_nav")
    page.click("#to-page2")
    page.wait_for_selector("#p2-btn", timeout=30000)
    time.sleep(0.6)
    page.click("#p2-btn")
    time.sleep(0.8)
    result["page2_value_after_bump"] = page.inner_text("#p2-value")
    result["page2_a_value"] = page.inner_text("#p2-a-value")
    page.click("#to-home")
    page.wait_for_selector("#a-btn", timeout=30000)
    time.sleep(0.8)
    after = snap(page, "post_nav")
    result["events"].append({"name": "nav_page2_and_back", "delta": diff(before, after)})
    result["after_nav_values"] = {
        "A": page.inner_text('[data-value="A"]'),
        "B": page.inner_text('[data-value="B"]'),
    }

    # --- M10: background task pushing to a page2-only substate while on page 1
    page.click("#storm2-btn")
    time.sleep(2.0)
    result["console_after_storm2"] = [c for c in console[-25:]]
    page.click("#to-page2")
    page.wait_for_selector("#p2-btn", timeout=30000)
    time.sleep(0.8)
    result["page2_value_after_bg_storm"] = page.inner_text("#p2-value")
    page.click("#p2-btn")
    time.sleep(0.8)
    result["page2_value_after_bg_storm_plus_click"] = page.inner_text("#p2-value")
    page.click("#to-home")
    page.wait_for_selector("#a-btn", timeout=30000)
    time.sleep(0.5)

    # --- M11: dynamic route
    page.click("#to-dyn")
    page.wait_for_selector("#dyn-pid", timeout=30000)
    time.sleep(0.6)
    result["dyn_pid"] = page.inner_text("#dyn-pid")
    result["dyn_a_value"] = page.inner_text("#dyn-a-value")
    page.click("#to-home")
    page.wait_for_selector("#a-btn", timeout=30000)
    time.sleep(0.5)

    # --- M12: rebuild 300 foreach rows
    before = snap(page, "pre_rows")
    trows = time.time()
    page.click("#rows-btn")
    page.wait_for_function(
        "() => document.querySelector('#rows li') && document.querySelector('#rows li').textContent.indexOf('row-0-') === 0",
        timeout=30000,
    )
    result["rows_rebuild_seconds"] = round(time.time() - trows, 3)
    time.sleep(0.8)
    after = snap(page, "post_rows")
    result["events"].append({"name": "rebuild_300_rows", "delta": diff(before, after)})

    # --- M13: reload and check storage hydration
    page.reload(wait_until="load")
    page.wait_for_selector("#ls-input", timeout=60000)
    time.sleep(2.0)
    result["storage_after_reload"] = {
        "ls": page.input_value("#ls-input"),
        "ss": page.input_value("#ss-input"),
        "ck": page.input_value("#ck-input"),
        "cs": page.input_value("#cs-input"),
        "ls_echo": page.inner_text("#ls-echo"),
        "ss_echo": page.inner_text("#ss-echo"),
        "ck_echo": page.inner_text("#ck-echo"),
    }
    snap(page, "after_reload")
    page.screenshot(path=str(OUT / f"{LABEL}_after_reload.png"))

    # --- M14: second tab
    page2_tab = ctx.new_page()
    page2_tab.goto(BASE + "/", wait_until="load")
    page2_tab.wait_for_selector("#ls-input", timeout=60000)
    time.sleep(2.0)
    result["tab2_storage"] = {
        "ls": page2_tab.input_value("#ls-input"),
        "ss": page2_tab.input_value("#ss-input"),
        "ck": page2_tab.input_value("#ck-input"),
    }
    result["tab2_A"] = page2_tab.inner_text('[data-value="A"]')
    page2_tab.close()

    # --- M15: direct load of page2 (no client nav)
    page3 = ctx.new_page()
    page3.goto(BASE + "/page2", wait_until="load")
    page3.wait_for_selector("#p2-btn", timeout=60000)
    time.sleep(1.5)
    page3.click("#p2-btn")
    time.sleep(1.0)
    result["direct_page2_value"] = page3.inner_text("#p2-value")
    page3.close()

    result["console"] = console
    result["page_errors"] = page_errors
    result["failed_requests"] = failed
    result["bad_responses"] = bad_responses
    result["ws_frame_counts"] = {
        "recv": sum(1 for f in ws_frames if f[0] == "recv"),
        "sent": sum(1 for f in ws_frames if f[0] == "sent"),
    }
    browser.close()

(OUT / f"{LABEL}_result.json").write_text(json.dumps(result, indent=2))
(OUT / f"{LABEL}_wsframes.txt").write_text(
    "\n".join(f"{k} {t:.3f} {f[:1500]}" for k, t, f in ws_frames)
)
print(json.dumps({k: v for k, v in result.items() if k not in ("marks", "onload_ws_frames", "console")}, indent=2)[:8000])
print("CONSOLE ERRORS:", json.dumps([c for c in console if c["type"] in ("error", "warning")], indent=1)[:4000])
