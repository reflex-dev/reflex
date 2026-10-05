import json, sys
from playwright.sync_api import sync_playwright
BASE=sys.argv[1].rstrip("/"); PHASE=sys.argv[2]
out={}
cons=[]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx=b.new_context(viewport={"width":1280,"height":900})
    pg=ctx.new_page()
    pg.on("console", lambda m: cons.append((m.type,m.text[:200])))
    pg.on("response", lambda r: out.setdefault("bad",[]).append({"url":r.url,"status":r.status}) if r.status>=400 else None)
    pg.goto(f"{BASE}/editor", wait_until="networkidle", timeout=60000)
    pg.wait_for_timeout(2500)
    out["portal_exists"]=pg.evaluate("()=>!!document.getElementById('portal')")
    out["portal_html"]=pg.evaluate("()=>{const e=document.getElementById('portal'); return e? e.outerHTML.slice(0,200): null}")
    out["portal_parent"]=pg.evaluate("()=>{const e=document.getElementById('portal'); return e? e.parentElement.tagName+'#'+(e.parentElement.id||'') : null}")
    out["body_children"]=pg.evaluate("()=>Array.from(document.body.children).map(e=>e.tagName+'#'+(e.id||'')+'.'+(e.className||'').slice(0,30))")
    out["carousel_css"]=pg.evaluate("""()=>{const o=[];for(const s of Array.from(document.styleSheets)){let r;try{r=s.cssRules}catch(e){continue}
      for(const rr of Array.from(r||[])){const t=rr.cssText||'';if(t.includes('carousel')){o.push(t.slice(0,100))}}}return o.slice(0,8)}""")
    box=pg.locator("#editor-box canvas").first.bounding_box()
    pg.mouse.click(box["x"]+55, box["y"]+60); pg.wait_for_timeout(500)
    pg.mouse.dblclick(box["x"]+55, box["y"]+60); pg.wait_for_timeout(1800)
    out["overlay_imgs"]=pg.eval_on_selector_all("img","els=>els.map(e=>e.getAttribute('src'))")
    out["carousel_root"]=pg.evaluate("()=>{const e=document.querySelector('.carousel-root, .carousel');return e? e.outerHTML.slice(0,300): null}")
    pg.screenshot(path=f"/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad/apps/components_bumps/shots/{PHASE}-portal-probe.png")
    b.close()
out["console"]=cons[-25:]
print(json.dumps(out, indent=2))
