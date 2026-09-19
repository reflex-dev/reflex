"""System color-scheme / ThemeProvider listener probe (#6180).

Fresh browser context (no stored color mode) so the app follows the OS preference.
Usage: python drive_colormode.py <base_url> <outdir> <label>
"""
import json, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE, OUT, LABEL = sys.argv[1].rstrip("/"), Path(sys.argv[2]), sys.argv[3]
OUT.mkdir(parents=True, exist_ok=True)
res = {"label": LABEL}
console, errors = [], []
INIT = "window.__renders = window.__renders || {};"

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context(color_scheme="light")
    ctx.add_init_script(INIT)
    pg = ctx.new_page()
    pg.on("console", lambda m: console.append((m.type, m.text[:300])))
    pg.on("pageerror", lambda e: errors.append(str(e)[:500]))
    pg.goto(BASE + "/", wait_until="load")
    pg.wait_for_selector("#cm-text", timeout=60000)
    time.sleep(2.0)
    res["initial"] = pg.inner_text("#cm-text")
    res["renders_initial"] = pg.evaluate("() => window.__renders")

    # flip the OS preference several times: the listener is attached once on mount
    seq = []
    for scheme in ["dark", "light", "dark", "light", "dark"]:
        pg.emulate_media(color_scheme=scheme)
        time.sleep(0.6)
        seq.append((scheme, pg.inner_text("#cm-text")))
    res["system_pref_sequence"] = seq
    res["renders_after_system"] = pg.evaluate("() => window.__renders")

    # now navigate client-side and flip again (listener must survive navigation)
    pg.click("#to-page2")
    pg.wait_for_selector("#p2-btn", timeout=30000)
    time.sleep(0.6)
    res["renders_on_page2"] = pg.evaluate("() => window.__renders")
    pg.click("#to-home")
    pg.wait_for_selector("#cm-text", timeout=30000)
    time.sleep(0.6)
    seq2 = []
    for scheme in ["light", "dark"]:
        pg.emulate_media(color_scheme=scheme)
        time.sleep(0.6)
        seq2.append((scheme, pg.inner_text("#cm-text")))
    res["system_pref_after_nav"] = seq2

    # a state event must not change the colormode consumer render count
    before = pg.evaluate("() => window.__renders['colormode']")
    for _ in range(5):
        pg.click("#a-btn")
    time.sleep(1.2)
    res["colormode_renders_from_5_state_events"] = pg.evaluate("() => window.__renders['colormode']") - before

    # router navigation must not re-render the evloop consumer more than the remount
    ev_before = pg.evaluate("() => window.__renders['evloop']")
    pg.click("#to-page2"); pg.wait_for_selector("#p2-btn", timeout=30000); time.sleep(0.5)
    pg.click("#to-home"); pg.wait_for_selector("#ev-btn", timeout=30000); time.sleep(0.8)
    res["evloop_renders_from_nav_roundtrip"] = pg.evaluate("() => window.__renders['evloop']") - ev_before

    pg.screenshot(path=str(OUT / f"{LABEL}_colormode_system.png"))
    res["console_err"] = [c for c in console if c[0] in ("error", "warning")]
    res["page_errors"] = errors
    b.close()

(OUT / f"{LABEL}_colormode.json").write_text(json.dumps(res, indent=2))
print(json.dumps(res, indent=2))
