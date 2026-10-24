"""Does a hostile `router.session.client_ip` render inert in the DOM? (verify_fh / HN-3)

Loads the hnet app's /ip page in Chromium. The browser's websocket must go through xff_proxy.py started with
`--mode none --add 'X-Forwarded-For: <payload>'` (and the server with trusted_proxy_hops=1 + REFLEX_API_URL
pointing at the proxy), so the backend selects the injected payload as client_ip. Then checks:
  #f_ip textContent == payload (verbatim), innerHTML is HTML-escaped, no child elements, the onerror / script
  side effects did not run, and the computed var + handler snapshot carry the same string.

Usage: xss_probe.py --url http://localhost:FP/ip --payload '<img src=x onerror=...>' [--out out.json]
"""

import argparse
import json
import os
import time

import playwright  # noqa: F401  venv guard
from playwright.sync_api import sync_playwright

assert f"/envs/{os.environ.get('DRV_VENV', 'driver')}/" in playwright.__file__, playwright.__file__

ap = argparse.ArgumentParser()
ap.add_argument("--url", required=True)
ap.add_argument("--payload", required=True)
ap.add_argument("--out", default=None)
a = ap.parse_args()

res = {"payload": a.payload, "console": [], "pageerrors": []}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    pg.on("console", lambda m: res["console"].append(f"{m.type}: {m.text}"[:300]))
    pg.on("pageerror", lambda e: res["pageerrors"].append(str(e)[:300]))
    pg.add_init_script("window.__pwned = 0; window.__onerror_calls = 0;")
    pg.goto(a.url)
    pg.wait_for_selector("#hydrated:has-text('true')", timeout=30000)
    time.sleep(1.0)
    pg.click("#rec")
    try:
        pg.wait_for_function("document.querySelectorAll('.seen').length >= 1", timeout=20000)
    except Exception as e:  # noqa: BLE001
        res["rec_timeout"] = str(e)[:200]
        res["n_text"] = pg.text_content("#n")
        res["hydrated_text"] = pg.text_content("#hydrated")
    time.sleep(0.5)
    res["f_ip_text"] = pg.text_content("#f_ip")
    res["f_ip_innerHTML"] = pg.inner_html("#f_ip")
    res["f_ip_child_elements"] = pg.evaluate("document.querySelector('#f_ip').children.length")
    res["cv_ip_text"] = pg.text_content("#cv_ip")
    seen = pg.query_selector_all(".seen")
    res["handler_snapshot_ip"] = json.loads(seen[0].text_content())["ip"] if seen else None
    res["img_elements_in_doc"] = pg.evaluate("document.querySelectorAll('img').length")
    res["script_elements_with_payload"] = pg.evaluate(
        "[...document.querySelectorAll('script')].filter(s => s.textContent.includes('__pwned')).length"
    )
    res["window.__pwned"] = pg.evaluate("window.__pwned")
    res["title"] = pg.title()
    b.close()

res["verdict"] = {
    "rendered_verbatim_as_text": res["f_ip_text"] == a.payload,
    "escaped_in_html": "&lt;" in res["f_ip_innerHTML"] and "<img" not in res["f_ip_innerHTML"],
    "no_child_elements": res["f_ip_child_elements"] == 0,
    "payload_did_not_execute": res["window.__pwned"] == 0 and res["img_elements_in_doc"] == 0,
    "same_string_in_computed_var_and_handler": res["cv_ip_text"] == a.payload == res["handler_snapshot_ip"],
}
print(json.dumps(res, indent=1, ensure_ascii=False))
if a.out:
    with open(a.out, "w") as fh:
        json.dump(res, fh, indent=1, ensure_ascii=False)
