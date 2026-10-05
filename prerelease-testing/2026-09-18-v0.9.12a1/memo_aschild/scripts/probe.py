"""Focused probes: class/style merge location, dropdown trigger on_click, boom page."""

import json
import os
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
OUT = sys.argv[2]
os.makedirs(OUT, exist_ok=True)
msgs = []
errs = []

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_context(viewport={"width": 1280, "height": 1000}).new_page()
    pg.on("console", lambda m: msgs.append({"t": m.type, "x": m.text}))
    pg.on("pageerror", lambda e: errs.append(str(e)))

    # ---- 1. where do class_name/style land on an as_child input?
    pg.goto(f"{BASE}/forms", wait_until="networkidle")
    pg.wait_for_timeout(1500)
    tree = pg.evaluate(
        """() => {
          const inp = document.querySelector('#inp_name');
          const out = [];
          let e = inp;
          for (let i=0; i<4 && e; i++) {
            const o = {tag:e.tagName, cls:e.className && e.className.toString(),
                       style: e.getAttribute('style'),
                       borderW: getComputedStyle(e).borderTopWidth,
                       borderC: getComputedStyle(e).borderTopColor,
                       attrs: e.getAttributeNames()};
            out.push(o); e = e.parentElement;
          }
          return out;
        }"""
    )
    print("ANCESTRY=" + json.dumps(tree, indent=1))
    print("HAS_OWN_CLASS_ANYWHERE=", pg.evaluate(
        "() => [...document.querySelectorAll('.own-class')].map(e=>e.tagName)"))

    # ---- 2. dropdown trigger
    pg.goto(f"{BASE}/triggers", wait_until="networkidle")
    pg.wait_for_timeout(1500)
    dd_html = pg.evaluate(
        """() => {const e=document.querySelector('#t_dropdown');
                  return e ? {outer: e.outerHTML.slice(0,700), parent: e.parentElement.tagName,
                              parentAttrs: e.parentElement.getAttributeNames()} : null;}"""
    )
    print("DROPDOWN_TRIGGER=" + json.dumps(dd_html, indent=1))
    before = pg.locator("#out_clicks").inner_text()
    pg.locator("#t_dropdown").click()
    pg.wait_for_timeout(2500)
    after = pg.locator("#out_clicks").inner_text()
    print(f"DROPDOWN clicks {before} -> {after}  log={pg.locator('#out_log').inner_text()}")
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(500)
    # click again
    before2 = pg.locator("#out_clicks").inner_text()
    pg.locator("#t_dropdown").click()
    pg.wait_for_timeout(2500)
    print(f"DROPDOWN 2nd clicks {before2} -> {pg.locator('#out_clicks').inner_text()}")
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(300)
    # compare: dialog trigger html
    dlg_html = pg.evaluate(
        """() => {const e=document.querySelector('#t_dialog');
                  return e ? e.outerHTML.slice(0,500) : null;}"""
    )
    print("DIALOG_TRIGGER=" + json.dumps(dlg_html))
    pg.screenshot(path=f"{OUT}/dropdown.png")

    # ---- 3. boom page
    msgs.clear()
    errs.clear()
    pg.goto(f"{BASE}/boom", wait_until="domcontentloaded")
    pg.wait_for_timeout(3000)
    print("BOOM_BODY=" + json.dumps(pg.locator("body").inner_text()[:800]))
    print("BOOM_HAS_BTN=", pg.locator("#btn_boom").count())
    print("BOOM_CONSOLE=" + json.dumps(msgs, indent=1)[:6000])
    print("BOOM_PAGEERRORS=" + json.dumps(errs)[:3000])
    invalid = [m for m in msgs if "Invalid DOM property" in m["x"]]
    print("INVALID_DOM_PROPERTY_MSGS=" + json.dumps(invalid, indent=1))
    pg.screenshot(path=f"{OUT}/boom.png")
    b.close()
