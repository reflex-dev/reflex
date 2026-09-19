import json, sys
from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
PHASE = sys.argv[2]
SHOTS = sys.argv[3]
out = {}
cons = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context(viewport={"width": 1280, "height": 900})
    pg = ctx.new_page()
    pg.on("console", lambda m: cons.append((m.type, m.text[:220])))
    pg.on("pageerror", lambda e: cons.append(("pageerror", str(e)[:220])))

    # --- ids page (issue 2)
    pg.goto(f"{BASE}/ids", wait_until="networkidle", timeout=90000)
    pg.wait_for_timeout(1500)
    out["foreach_ids"] = pg.eval_on_selector_all("#ids-box .foreach-input", "els=>els.map(e=>e.id)")
    out["foreach_labels"] = pg.eval_on_selector_all("#ids-box .foreach-label", "els=>els.map(e=>({for:e.htmlFor, text:e.textContent}))")
    out["memo_ids"] = pg.eval_on_selector_all("#memo-box .memo-input", "els=>els.map(e=>e.id)")
    out["label_resolution"] = pg.evaluate("""()=>Array.from(document.querySelectorAll('#ids-box .foreach-label')).map(l=>{
        const t=document.getElementById(l.htmlFor); return {for:l.htmlFor, text:l.textContent, targetValue: t? t.value : null};})""")
    # click each label, see which input gets focus
    res = []
    for i in range(3):
        lab = pg.locator("#ids-box .foreach-label").nth(i)
        lab.click()
        pg.wait_for_timeout(150)
        res.append(pg.evaluate("()=>document.activeElement ? (document.activeElement.value||document.activeElement.tagName) : null"))
    out["label_click_focus_values"] = res
    out["dup_id_check"] = pg.evaluate("""()=>{const ids=Array.from(document.querySelectorAll('[id]')).map(e=>e.id);
        const seen={},dups=[]; for(const i of ids){ if(seen[i]) {if(!dups.includes(i))dups.push(i);} seen[i]=1;} return {total:ids.length, dups};}""")
    pg.screenshot(path=f"{SHOTS}/{PHASE}-ids.png")

    # --- editor page (issue 1)
    pg.goto(f"{BASE}/editor", wait_until="networkidle", timeout=90000)
    pg.wait_for_timeout(2500)
    out["portal_exists"] = pg.evaluate("()=>!!document.getElementById('portal')")
    out["portal_html"] = pg.evaluate("()=>{const e=document.getElementById('portal'); return e? e.outerHTML.slice(0,200): null}")
    out["portal_parent"] = pg.evaluate("()=>{const e=document.getElementById('portal'); return e? e.parentElement.tagName+'#'+(e.parentElement.id||'') : null}")
    out["body_children"] = pg.evaluate("()=>Array.from(document.body.children).map(e=>e.tagName+'#'+(e.id||'')+'.'+String(e.className||'').slice(0,30))")
    out["badge_present"] = pg.evaluate("()=>!!document.querySelector('a[aria-label=\"Built with Reflex\"]')")
    out["carousel_css_rules"] = pg.evaluate("""()=>{let n=0;for(const s of Array.from(document.styleSheets)){let r;try{r=s.cssRules}catch(e){continue}
      for(const rr of Array.from(r||[])){if((rr.cssText||'').includes('carousel'))n++;}}return n;}""")
    cvs = pg.locator("#editor-box canvas").first
    box = cvs.bounding_box()
    out["canvas_box"] = box
    pg.mouse.click(box["x"] + 55, box["y"] + 60)
    pg.wait_for_timeout(400)
    pg.mouse.dblclick(box["x"] + 55, box["y"] + 60)
    pg.wait_for_timeout(2000)
    out["overlay_imgs"] = pg.eval_on_selector_all("img", "els=>els.map(e=>e.getAttribute('src'))")
    out["carousel_root"] = pg.evaluate("()=>{const e=document.querySelector('.carousel-root, .carousel'); return e? e.outerHTML.slice(0,250): null}")
    out["gdg_overlay"] = pg.evaluate("()=>{const e=document.querySelector('.gdg-overlay-editor, [class*=overlay-editor]'); return e? e.className : null}")
    pg.screenshot(path=f"{SHOTS}/{PHASE}-editor-overlay.png")
    b.close()
out["console"] = cons[-30:]
print(json.dumps(out, indent=2))
