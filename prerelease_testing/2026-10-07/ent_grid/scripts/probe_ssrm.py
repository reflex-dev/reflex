"""Probe the SSRM ModelWrapper page: login, reload, record every datasource response.

Usage: probe_ssrm.py <base_url> <out_dir> <expected_venv> <label>
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from qa_common import Session, assert_driver_and_server  # noqa: E402

base, out, venv, label = sys.argv[1:5]
generate = len(sys.argv) > 5 and sys.argv[5] == "generate"
info = assert_driver_and_server(venv)

ROWS_JS = "() => [...document.querySelectorAll('.ag-row .ag-cell[col-id=\"name\"]')].map(c => c.innerText.trim()).filter(Boolean).length"

with Session(f"probe_ssrm-{label}", Path(out)) as s:
    s.note(f"guard: {info['versions']}")
    p = s.new_page(label="ssrm")
    t0 = time.time()
    log = []

    def on_resp(r):
        if "abstract-wrapper-data" in r.url:
            try:
                t = r.text()
                b = t[:100] + " ... " + t[-60:]
            except Exception as e:  # noqa: BLE001
                b = repr(e)
            log.append((round(time.time() - t0, 2), r.status, b))

    p.on("response", on_resp)
    p.goto(base + "/model-ssrm", wait_until="networkidle")
    p.wait_for_timeout(2000)
    s.note(f"initial: rows={p.evaluate(ROWS_JS)} buttons={p.locator('button').all_inner_texts()[:4]}")
    if p.locator("button:has-text('Login')").count():
        p.click("button:has-text('Login')")
        p.wait_for_timeout(3000)
    s.note(f"after login: rows={p.evaluate(ROWS_JS)}")
    if generate:
        n0 = len(log)
        p.click("button:has-text('Generate Friends')")
        p.wait_for_timeout(4000)
        s.note(f"after generate: rows={p.evaluate(ROWS_JS)} responses={log[n0:]}")
        s.shot(p, "after-generate")
    s.shot(p, "after-login")
    for i in range(3):
        n0 = len(log)
        p.reload(wait_until="networkidle")
        for w in (1000, 3000, 6000):
            p.wait_for_timeout(w)
        s.note(f"reload {i}: rows={p.evaluate(ROWS_JS)} logout_btn={p.locator('button:has-text(\"Logout\")').count()} responses={log[n0:]}")
        s.check(f"ssrm reload {i}: rows render while logged in", p.evaluate(ROWS_JS) > 0, p.evaluate(ROWS_JS))
        s.shot(p, f"reload{i}")
    # client-side navigation away and back
    p.click("text=SSRM ModelWrapper")
    p.wait_for_timeout(800)
    s.note("dropdown opened")
    p.keyboard.press("Escape")
    p.goto(base + "/model", wait_until="networkidle")
    p.wait_for_timeout(1500)
    n0 = len(log)
    p.evaluate("() => window.history.back()")
    p.wait_for_timeout(5000)
    s.note(f"history back: rows={p.evaluate(ROWS_JS)} responses={log[n0:]}")
    # logout/login toggle as a forced refresh
    n0 = len(log)
    p.click("button:has-text('Logout')")
    p.wait_for_timeout(2500)
    p.click("button:has-text('Login')")
    p.wait_for_timeout(4000)
    s.note(f"logout+login toggle: rows={p.evaluate(ROWS_JS)} responses={log[n0:]}")
    s.check("ssrm: logout+login toggle re-mount shows rows", p.evaluate(ROWS_JS) > 0, p.evaluate(ROWS_JS))
    s.shot(p, "toggle")
