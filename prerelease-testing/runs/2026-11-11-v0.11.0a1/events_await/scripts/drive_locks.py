"""Lock hygiene around awaited handlers: after each scenario, time a `ping` round trip.

usage: drive_locks.py <frontend_url> <server_log> <out.json>
"""
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

URL, LOG, OUT = sys.argv[1].rstrip("/"), Path(sys.argv[2]), Path(sys.argv[3])
IDS = ["result", "total", "progress", "mlog", "query"]
SPY = """
window.__hist = [];
new MutationObserver(() => {
  const r = document.getElementById('result'); if (!r) return;
  const h = window.__hist; if (!h.length || h[h.length-1][1] !== r.textContent) h.push([Date.now(), r.textContent]);
}).observe(document, {childList: true, subtree: true, characterData: true});
"""
results = {}


def snap(page):
    return page.evaluate("(ids) => Object.fromEntries(ids.map(i => [i, document.getElementById(i)?.textContent ?? null]))", IDS)


def hist(page, t0):
    return page.evaluate("(s) => window.__hist.filter(h => h[0] >= s).map(h => [Math.round(h[0]-s), h[1]])", t0 * 1000)


def ping(page, timeout=25):
    t0 = time.time()
    page.click("#b-ping")
    try:
        page.wait_for_function("() => (document.getElementById('result')?.textContent ?? '').startsWith('ping:')", timeout=timeout * 1000)
    except Exception:
        return None
    return round(time.time() - t0, 3)


def reset(page):
    page.click("#b-reset")
    page.wait_for_function("() => document.getElementById('result')?.textContent === 'reset: ok'", timeout=30000)
    time.sleep(0.2)


def scenario(page, name, clicks, wait, gap=0.5, expect_ping_under=None):
    reset(page)
    off, t0 = LOG.stat().st_size, time.time()
    for i, c in enumerate(clicks):
        if i:
            time.sleep(gap)
        page.click(c)
    time.sleep(wait)
    s = snap(page)
    lat = ping(page)
    time.sleep(0.3)
    with LOG.open("rb") as f:
        f.seek(off)
        log = f.read().decode(errors="replace")
    errs = sorted({l.strip()[:140] for l in log.splitlines() if "Error" in l and "File " not in l})
    results[name] = {"snap": s, "ping_s": lat, "hist_ms": hist(page, t0), "errors_in_log": errs, "log_tail": log[-3000:]}
    print(f"{name:26s} ping={lat}s snap={ {k: v for k, v in s.items() if v not in ('', '0', None)} }")
    print(f"{'':26s} hist={hist(page, t0)}")
    print(f"{'':26s} log-errors={errs[:4]}", flush=True)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = browser.new_context().new_page()
    page.add_init_script(SPY)
    page.goto(URL + "/")
    page.wait_for_selector("#b-reset")
    time.sleep(1.5)
    # ping is measured right after `wait`; the inline slow() tasks take 1 s, so a ping that needs ~1 s is the lock doing its job
    scenario(page, "gather_boom", ["#b-k_gather_boom"], 0.3)
    scenario(page, "future_then_raise", ["#b-k_future_then_raise"], 0.3)
    scenario(page, "sup_outer_x2", ["#b-k_sup_outer-a", "#b-k_sup_outer-b"], 0.5)
    scenario(page, "sup_outer_x2_settled", ["#b-k_sup_outer-a", "#b-k_sup_outer-b"], 4.0)
    scenario(page, "bg_future", ["#b-k_bg_future"], 0.3)
    scenario(page, "bg_wait_for", ["#b-k_bg_wait_for"], 1.0)
    scenario(page, "bg_sup_x2", ["#b-k_bg_sup-a", "#b-k_bg_sup-b"], 0.5)
    scenario(page, "bg_sup_x2_settled", ["#b-k_bg_sup-a", "#b-k_bg_sup-b"], 4.5)
    scenario(page, "nested_gen", ["#b-k_nested_gen"], 1.0)
    # reload the page while a handler is awaiting a slow handler
    reset(page)
    off, t0 = LOG.stat().st_size, time.time()
    page.click("#b-k_slow_nav")
    time.sleep(0.5)
    page.reload()
    page.wait_for_selector("#b-reset")
    t_reload = time.time()
    page.wait_for_function("() => (document.getElementById('token')?.textContent ?? '').length > 10", timeout=30000)
    hydrated = round(time.time() - t_reload, 3)
    time.sleep(2.5)
    s = snap(page)
    lat = ping(page)
    with LOG.open("rb") as f:
        f.seek(off)
        log = f.read().decode(errors="replace")
    errs = sorted({l.strip()[:140] for l in log.splitlines() if "Error" in l and "File " not in l})
    results["reload_during_await"] = {"snap": s, "ping_s": lat, "hydrate_s": hydrated, "errors_in_log": errs, "log_tail": log[-3000:]}
    print(f"reload_during_await        hydrate={hydrated}s ping={lat}s snap={s} log-errors={errs[:4]}")
    browser.close()
OUT.write_text(json.dumps(results, indent=1))
