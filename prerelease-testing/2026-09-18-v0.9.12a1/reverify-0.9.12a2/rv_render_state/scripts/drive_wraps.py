"""Check app-wrap presence in the DOM. Usage: drive_wraps.py <url> <outdir> <label>"""
import json, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE, OUT, LABEL = sys.argv[1].rstrip("/"), Path(sys.argv[2]), sys.argv[3]
OUT.mkdir(parents=True, exist_ok=True)
res = {"label": LABEL, "console": [], "page_errors": [], "failed": [], "bad": []}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context(); pg = ctx.new_page()
    pg.on("console", lambda m: res["console"].append({"type": m.type, "text": m.text[:300]}))
    pg.on("pageerror", lambda e: res["page_errors"].append(str(e)[:500]))
    pg.on("requestfailed", lambda r: res["failed"].append({"url": r.url, "err": str(r.failure)}))
    pg.on("response", lambda r: res["bad"].append({"url": r.url, "status": r.status}) if r.status >= 400 else None)
    pg.goto(BASE + "/", wait_until="load")
    pg.wait_for_selector("#hello", timeout=90000)
    time.sleep(2.5)
    res["wraps"] = pg.evaluate("""() => {
      const q = (s) => !!document.querySelector(s);
      const wraps = [...document.querySelectorAll('[data-wrap]')].map(e => e.getAttribute('data-wrap'));
      const badge = document.querySelector('a[href*="reflex.dev"]');
      return {
        custom_wraps: wraps,
        portal: q('#portal'),
        badge: !!badge,
        badge_text: badge ? badge.innerText.trim().slice(0,40) : null,
        toaster: q('[data-sonner-toaster]') || q('.toaster') || q('section[aria-label*="otification"]'),
        grid: q('#grid'),
      };
    }""")
    pg.click("#b_toast")
    time.sleep(1.5)
    res["after_toast"] = pg.evaluate("""() => ({
      n: document.querySelector('#v_n') ? document.querySelector('#v_n').innerText : null,
      toasts: document.querySelectorAll('[data-sonner-toast]').length,
      toast_text: [...document.querySelectorAll('[data-sonner-toast]')].map(e => e.innerText.replace(/\\n/g,' ').slice(0,40)),
      toaster_present: !!document.querySelector('[data-sonner-toaster]'),
    })""")
    pg.screenshot(path=str(OUT / f"{LABEL}_wraps.png"))
    res["root_html_head"] = pg.evaluate("() => document.body.innerHTML.slice(0, 1200)")
    ctx.close(); b.close()
(OUT / f"{LABEL}_wraps.json").write_text(json.dumps(res, indent=1))
print(json.dumps({k: v for k, v in res.items() if k != "root_html_head"}, indent=1))
