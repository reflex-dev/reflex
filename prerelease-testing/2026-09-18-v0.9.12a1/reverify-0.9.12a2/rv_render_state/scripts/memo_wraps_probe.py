"""Badge + app-wrap coexistence on the memo_aschild app. Usage: <url> <outdir> <label>"""
import json, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright
BASE, OUT, LABEL = sys.argv[1].rstrip("/"), Path(sys.argv[2]), sys.argv[3]
OUT.mkdir(parents=True, exist_ok=True)
res = {"label": LABEL, "console": [], "page_errors": []}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context(); pg = ctx.new_page()
    pg.on("console", lambda m: res["console"].append({"type": m.type, "text": m.text[:300]}))
    pg.on("pageerror", lambda e: res["page_errors"].append(str(e)[:400]))
    pg.goto(BASE + "/memoapp", wait_until="load")
    pg.wait_for_selector("#btn_toast", timeout=90000)
    time.sleep(2.5)
    res["before"] = pg.evaluate("""() => {
      const badge = document.querySelector('a[href*="reflex.dev"]');
      return {
        badge: !!badge, badge_text: badge ? badge.innerText.trim() : null,
        badge_parent: badge ? badge.parentElement.tagName + '#' + (badge.parentElement.id||'') : null,
        toaster: !!document.querySelector('[data-sonner-toaster]'),
        overlay_present: !!document.querySelector('[data-sonner-toaster]') || !!document.querySelector('section[aria-label*="otification"]'),
        uploads: document.querySelectorAll('input[type=file]').length,
        body_children: [...document.body.children].map(e => e.tagName + (e.id ? '#'+e.id : '') + (e.getAttribute('data-sonner-toaster') ? '[sonner]' : '')),
      };
    }""")
    pg.click("#btn_toast")
    time.sleep(1.5)
    res["after_toast"] = pg.evaluate("""() => ({
      toasts: document.querySelectorAll('[data-sonner-toast]').length,
      texts: [...document.querySelectorAll('[data-sonner-toast]')].map(e => e.innerText.replace(/\\n/g,' ').slice(0,30)),
      badge_still: !!document.querySelector('a[href*="reflex.dev"]'),
    })""")
    pg.screenshot(path=str(OUT / f"{LABEL}_memo_wraps.png"))
    ctx.close(); b.close()
(OUT / f"{LABEL}_memo_wraps.json").write_text(json.dumps(res, indent=1))
print(json.dumps(res, indent=1))
