import json, sys
from playwright.sync_api import sync_playwright
BASE=sys.argv[1].rstrip("/"); PHASE=sys.argv[2]; SHOTS=sys.argv[3]
cons=[]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg=b.new_context(viewport={"width":1280,"height":900}).new_page()
    pg.on("console", lambda m: cons.append((m.type,m.text[:200])))
    pg.goto(f"{BASE}/editor", wait_until="networkidle", timeout=90000); pg.wait_for_timeout(2500)
    out={
      "portal_exists": pg.evaluate("()=>!!document.getElementById('portal')"),
      "portal_parent": pg.evaluate("()=>{const e=document.getElementById('portal');return e?e.parentElement.tagName:null}"),
      "badge_present": pg.evaluate("()=>!!document.querySelector('a[href=\"https://reflex.dev\"]')"),
      "carousel_css_rules": pg.evaluate("""()=>{let n=0;for(const s of Array.from(document.styleSheets)){let r;try{r=s.cssRules}catch(e){continue}
        for(const rr of Array.from(r||[])){if((rr.cssText||'').includes('carousel'))n++;}}return n;}"""),
    }
    box=pg.locator("#editor-box canvas").first.bounding_box()
    pg.mouse.click(box["x"]+55, box["y"]+60); pg.wait_for_timeout(400)
    pg.mouse.dblclick(box["x"]+55, box["y"]+60); pg.wait_for_timeout(2000)
    out["overlay_imgs"]=pg.eval_on_selector_all("img","els=>els.map(e=>e.getAttribute('src'))")
    out["carousel_root"]=pg.evaluate("()=>{const e=document.querySelector('.carousel-root, .carousel');return e?e.outerHTML.slice(0,160):null}")
    out["gdg_overlay_any"]=pg.evaluate("()=>{const e=document.querySelector('[class*=gdg-]');return e?e.className:null}")
    pg.screenshot(path=f"{SHOTS}/{PHASE}-editor.png")
    b.close()
out["console_errors"]=[c[1] for c in cons if c[0]=="error"]
print(json.dumps(out, indent=2))
