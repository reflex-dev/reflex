import json, sys
from playwright.sync_api import sync_playwright

URL, SHOTS, TAG = sys.argv[1], sys.argv[2], sys.argv[3]
console_msgs, page_errors, bad = [], [], []

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context(); page = ctx.new_page()
    page.on("console", lambda m: console_msgs.append({"t": m.type, "x": m.text[:300]}))
    page.on("pageerror", lambda e: page_errors.append(str(e)[:400]))
    page.on("response", lambda r: bad.append({"u": r.url[:140], "s": r.status}) if r.status >= 400 else None)

    def txt(sel):
        try: return page.inner_text(sel, timeout=4000)
        except Exception as e: return f"<MISS {sel} {type(e).__name__}>"

    page.goto(URL, wait_until="networkidle", timeout=90000)
    page.wait_for_timeout(2000)
    print("mods at import:", txt("#mods-import"))
    print("mods after data import:", txt("#mods-after"))
    print("mods now:", txt("#mods-now"))
    print("initial dt:", txt("#dt")[:200])
    page.screenshot(path=f"{SHOTS}/{TAG}_data_01_initial.png", full_page=True)

    def shot(n): page.screenshot(path=f"{SHOTS}/{TAG}_data_{n}.png", full_page=True)

    page.click("#btn-df"); page.wait_for_timeout(1800)
    print("after df status:", txt("#status"), "| hasrows:", txt("#hasrows"))
    print("dt text:", txt("#dt")[:300].replace("\n", " "))
    print("dt cells:", page.eval_on_selector_all("#dt td", "els=>els.map(e=>e.textContent).slice(0,12)"))

    page.click("#btn-fig"); page.wait_for_timeout(2500)
    print("after fig status:", txt("#status"))
    print("plotly svg count:", page.eval_on_selector_all("#plot svg", "e=>e.length"))
    print("plotly bars:", page.eval_on_selector_all("#plot .trace .point, #plot g.bars path", "e=>e.length"))
    print("plotly title:", page.eval_on_selector_all("#plot .gtitle", "e=>e.map(x=>x.textContent)"))

    page.click("#btn-img"); page.wait_for_timeout(1500)
    src = page.eval_on_selector("#imgbox img", "e=>e.src")
    print("after img status:", txt("#status"), "| img src prefix:", src[:40], "| len:", len(src))
    print("img natural size:", page.eval_on_selector("#imgbox img", "e=>[e.naturalWidth,e.naturalHeight]"))
    shot("02_all_three")

    page.click("#btn-all"); page.wait_for_timeout(3000)
    print("after ALL status:", txt("#status"), "| dt cells:", page.eval_on_selector_all("#dt td", "e=>e.map(x=>x.textContent).slice(0,8)"))
    print("plotly title after all:", page.eval_on_selector_all("#plot .gtitle", "e=>e.map(x=>x.textContent)"))
    src2 = page.eval_on_selector("#imgbox img", "e=>e.src")
    print("img changed:", src2 != src)
    shot("03_after_all")

    page.click("#btn-bg"); page.wait_for_timeout(3500)
    print("bg status:", txt("#bg-status"), "| dt cells:", page.eval_on_selector_all("#dt td", "e=>e.map(x=>x.textContent).slice(0,9)"))
    print("mods now after bg:", txt("#mods-now"))
    shot("04_after_bg")

    page.click("#btn-cs"); page.wait_for_timeout(900)
    page.click("#btn-cs"); page.wait_for_timeout(900)
    print("ComponentState button:", txt("#btn-cs"))
    print("memo caption:", txt(".memo-caption"))

    page.reload(wait_until="networkidle"); page.wait_for_timeout(2500)
    print("after reload: status:", txt("#status"), "| dt cells:", page.eval_on_selector_all("#dt td", "e=>e.map(x=>x.textContent).slice(0,6)"))
    print("after reload img src len:", len(page.eval_on_selector("#imgbox img", "e=>e.src")))
    shot("05_after_reload")
    b.close()

print("\n=== CONSOLE err/warn ===")
for m in console_msgs:
    if m["t"] in ("error", "warning"): print(m)
print("PAGE ERRORS:", json.dumps(page_errors, indent=1))
print("BAD RESPONSES:", json.dumps(bad, indent=1))
print("TOTAL CONSOLE:", len(console_msgs))
