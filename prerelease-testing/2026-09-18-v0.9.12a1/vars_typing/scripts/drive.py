"""Playwright driver for the vars_typing app: captures console, page errors, failed requests."""
import json, sys, time
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3340"
TAG = sys.argv[2] if len(sys.argv) > 2 else "dev"
SHOTS = sys.argv[3] if len(sys.argv) > 3 else "/tmp"

console, errors, failed, bad_resp = [], [], [], []
report = {"base": BASE, "tag": TAG, "steps": []}

def step(name, **kw):
    report["steps"].append({"step": name, **kw})
    print(f"[{name}] {json.dumps(kw, default=str)[:400]}")

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    page = ctx.new_page()
    page.on("console", lambda m: console.append({"type": m.type, "text": m.text[:400]}))
    page.on("pageerror", lambda e: errors.append(str(e)[:400]))
    page.on("requestfailed", lambda r: failed.append({"url": r.url[:200], "err": str(r.failure)[:200]}))
    page.on("response", lambda r: bad_resp.append({"url": r.url[:200], "status": r.status}) if r.status >= 400 else None)

    def txt(sel, timeout=8000):
        try:
            return page.locator(sel).first.inner_text(timeout=timeout)
        except Exception as e:
            return f"<ERR {type(e).__name__}>"

    def shot(n):
        page.screenshot(path=f"{SHOTS}/{TAG}_{n}.png", full_page=False)

    # ---------- / ----------
    page.goto(BASE + "/", wait_until="networkidle", timeout=90000)
    page.wait_for_timeout(2500)
    step("index_loaded", title=page.title(),
         desc=page.eval_on_selector("meta[name=description]", "e=>e.content") if page.query_selector("meta[name=description]") else None,
         hash_line=txt("#hash_line"), hook_ran=page.evaluate("() => !!window.__vt_hook_ran"),
         colormode=txt("#colormode_line"), count=txt("#count"), doubled=txt("#doubled"),
         cs_value=txt("#cs_value"), memo=txt("#memo_line"), cond=txt("#cond_line"))
    shot("01_index")

    # inc x3 -> computed var + cond flip
    for _ in range(3):
        page.click("#inc"); page.wait_for_timeout(250)
    step("after_inc3", count=txt("#count"), doubled=txt("#doubled"), cond=txt("#cond_line"))

    # #6923: change the State title at runtime
    page.click("#settitle"); page.wait_for_timeout(900)
    step("after_settitle", doc_title=page.title(),
         meta_desc=page.eval_on_selector("meta[name=description]", "e=>e.content") if page.query_selector("meta[name=description]") else None,
         title_val=txt("#title_val"))
    shot("02_title_changed")

    # event chain
    page.click("#chain"); page.wait_for_timeout(1200)
    step("after_chain", count=txt("#count"), doc_title=page.title(), log=txt("#log"))

    # background task
    page.click("#bg"); page.wait_for_timeout(1800)
    step("after_bg", bg_ticks=txt("#bg_ticks"))

    # annotated handler arg
    page.click("#take"); page.wait_for_timeout(700)
    step("after_take", limit=txt("#limit"), log=txt("#log"))

    # ComponentState
    page.click("#cs_bump"); page.click("#cs_bump"); page.wait_for_timeout(600)
    step("after_cs_bump", cs_counter=txt("#cs_counter"))

    # client_state
    page.click("#cs_btn"); page.wait_for_timeout(600)
    step("after_client_state", cs_value=txt("#cs_value"))

    # ---------- /pets (#7189) client-side nav ----------
    page.click("#nav_pets"); page.wait_for_timeout(2000)
    step("pets_loaded", doc_title=page.title(), pet_name=txt("#pet_name"), pet_kind=txt("#pet_kind"),
         sound=txt("#pet_sound"), cond=txt("#pet_cond"), pet0=txt("#pet_0"), pet1=txt("#pet_1"),
         pets_len=txt("#pets_len"))
    shot("03_pets")
    page.click("#to_dog"); page.wait_for_timeout(800)
    step("pets_to_dog", pet_name=txt("#pet_name"), pet_kind=txt("#pet_kind"), sound=txt("#pet_sound"), cond=txt("#pet_cond"))
    page.click("#add_pet"); page.wait_for_timeout(800)
    step("pets_add", pets_len=txt("#pets_len"), pet2=txt("#pet_2"))
    page.click("#to_cat"); page.wait_for_timeout(800)
    step("pets_to_cat", pet_name=txt("#pet_name"), sound=txt("#pet_sound"))
    shot("04_pets_after")

    # ---------- /second: client-side nav between State-titled pages (#6923) ----------
    page.click("#nav_second"); page.wait_for_timeout(1500)
    step("second_loaded", doc_title=page.title(), title_val=txt("#title_val"), count=txt("#count"),
         meta_desc=page.eval_on_selector("meta[name=description]", "e=>e.content") if page.query_selector("meta[name=description]") else None)
    page.click("#inc"); page.wait_for_timeout(500)
    page.click("#nav_home"); page.wait_for_timeout(1500)
    step("back_home", doc_title=page.title(), count=txt("#count"), hook_ran=page.evaluate("() => !!window.__vt_hook_ran"))
    shot("05_back_home")

    # ---------- /heavy (#7198 volume) ----------
    t0 = time.time()
    page.goto(BASE + "/heavy", wait_until="networkidle", timeout=120000)
    page.wait_for_timeout(1500)
    step("heavy_loaded", load_s=round(time.time()-t0, 2), h0=txt("#heavy_0"), h1=txt("#heavy_1"), h2=txt("#heavy_2"),
         n_texts=page.evaluate("() => document.querySelectorAll('.rt-Text').length"))
    shot("06_heavy")

    # ---------- direct load of /pets (SSR path) ----------
    page.goto(BASE + "/pets", wait_until="networkidle", timeout=90000)
    page.wait_for_timeout(2000)
    step("pets_direct", doc_title=page.title(), pet_name=txt("#pet_name"), sound=txt("#pet_sound"))

    # ---------- direct load of / in a second tab (fresh state) ----------
    p2 = ctx.new_page()
    p2.goto(BASE + "/", wait_until="networkidle", timeout=90000)
    p2.wait_for_timeout(2500)
    step("second_tab", doc_title=p2.title(), count=p2.locator("#count").first.inner_text(),
         hook_ran=p2.evaluate("() => !!window.__vt_hook_ran"),
         desc=p2.eval_on_selector("meta[name=description]", "e=>e.content") if p2.query_selector("meta[name=description]") else None)
    p2.screenshot(path=f"{SHOTS}/{TAG}_07_tab2.png")

    ctx.close(); b.close()

report["console"] = console
report["page_errors"] = errors
report["failed_requests"] = failed
report["bad_responses"] = bad_resp
print("\n=== CONSOLE ===")
for c in console:
    print(f"  {c['type']}: {c['text'][:250]}")
print("=== PAGE ERRORS ===", json.dumps(errors, indent=2)[:2000])
print("=== FAILED REQUESTS ===", json.dumps(failed, indent=2)[:1500])
print("=== BAD RESPONSES ===", json.dumps(bad_resp, indent=2)[:1500])
with open(f"{SHOTS}/{TAG}_report.json", "w") as f:
    json.dump(report, f, indent=2, default=str)
