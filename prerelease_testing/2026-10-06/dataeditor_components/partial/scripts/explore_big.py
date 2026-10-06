"""Investigate wheel scrolling on the 5,000-row grid."""
import json
import sys
import time

import playwright

assert "/scratchpad/envs/driver/" in playwright.__file__, playwright.__file__
from playwright.sync_api import sync_playwright  # noqa: E402

base = sys.argv[1]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page(viewport={"width": 1280, "height": 900})
    pg.add_init_script("window.__lt=[]; try{new PerformanceObserver(l=>{for(const e of l.getEntries()) window.__lt.push([Math.round(e.startTime), Math.round(e.duration)])}).observe({type:'longtask', buffered:true})}catch(e){}")
    pg.goto(base + "/de-big", wait_until="domcontentloaded", timeout=120000)
    pg.wait_for_selector("#de-big-box canvas", timeout=120000)
    t0 = time.time()
    while "5000" not in pg.locator("#big-count").inner_text() and time.time() - t0 < 30:
        pg.wait_for_timeout(200)
    pg.wait_for_timeout(2000)
    print("longtasks during load:", pg.evaluate("window.__lt"))
    pg.evaluate("window.__lt=[]")
    box = pg.locator("#de-big-box canvas").first.bounding_box()
    info = pg.evaluate("""() => { const s = document.querySelector('#de-big-box .dvn-scroller'); const r = s.getBoundingClientRect();
      const el = document.elementFromPoint(r.x + 200, r.y + 200);
      return {scroller_rect: [r.x, r.y, r.width, r.height], scrollTop: s.scrollTop, overflowY: getComputedStyle(s).overflowY, el_at_point: el ? el.tagName + '.' + el.className : null}; }""")
    print("scroller:", json.dumps(info))
    print("canvas box:", box)
    pg.mouse.move(box["x"] + 200, box["y"] + 200)
    res = []
    for i in range(5):
        t = time.time()
        pg.mouse.wheel(0, 600)
        pg.wait_for_timeout(300)
        res.append((round(time.time() - t, 3), pg.evaluate("document.querySelector('#de-big-box .dvn-scroller').scrollTop")))
    print("wheel results (sec, scrollTop):", res)
    print("longtasks during wheel:", pg.evaluate("window.__lt"))
    pg.evaluate("window.__lt=[]")
    t = time.time()
    pg.evaluate("document.querySelector('#de-big-box .dvn-scroller').scrollTop = 50000")
    pg.wait_for_timeout(500)
    print("programmatic scroll ->", pg.evaluate("document.querySelector('#de-big-box .dvn-scroller').scrollTop"), "longtasks:", pg.evaluate("window.__lt"))
    b.close()
