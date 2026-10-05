import json, sys, time
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3420/"
SHOTS = sys.argv[2] if len(sys.argv) > 2 else "/tmp/shots"
TAG = sys.argv[3] if len(sys.argv) > 3 else "dev"

console_msgs, page_errors, bad_responses, ws_frames = [], [], [], []

def txt(sel, page):
    try:
        return page.inner_text(sel, timeout=3000)
    except Exception as e:
        return f"<MISSING {sel}: {type(e).__name__}>"

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    page = ctx.new_page()
    page.on("console", lambda m: console_msgs.append({"type": m.type, "text": m.text[:400]}))
    page.on("pageerror", lambda e: page_errors.append(str(e)[:500]))
    page.on("response", lambda r: bad_responses.append({"url": r.url[:160], "status": r.status}) if r.status >= 400 else None)
    def on_ws(ws):
        ws.on("framereceived", lambda pl: ws_frames.append(("recv", str(pl)[:3000])))
    page.on("websocket", on_ws)

    page.goto(URL, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(1500)
    print("=== modules at import:", txt("#mods-import", page))
    print("=== modules now (on_load):", txt("#mods-now", page))
    page.screenshot(path=f"{SHOTS}/{TAG}_01_initial.png")

    def click(sel, label, wait=1800):
        page.click(sel, timeout=10000)
        page.wait_for_timeout(wait)
        print(f"--- after {label}: log={txt('#log-out', page)}")

    click("#btn-seed", "seed")
    click("#btn-sync", "sync load", 2500)
    print("count:", txt("#count", page))
    print("books text:", txt("#books", page)[:600])
    print("single-book:", txt("#single-book", page))
    page.screenshot(path=f"{SHOTS}/{TAG}_02_sync.png", full_page=True)

    # relationship field access must show real names, not blanks
    authors_rendered = page.eval_on_selector_all(".author-name", "els => els.map(e => e.textContent)")
    countries = page.eval_on_selector_all(".author-country", "els => els.map(e => e.textContent)")
    tags = page.eval_on_selector_all(".tag-badge", "els => els.map(e => e.textContent)")
    print("AUTHOR_NAMES:", authors_rendered)
    print("AUTHOR_COUNTRIES:", countries)
    print("TAG_BADGES:", tags)

    click("#btn-async", "async load", 2500)
    print("authors box:", txt("#authors", page)[:500])
    page.screenshot(path=f"{SHOTS}/{TAG}_03_async.png", full_page=True)

    click("#btn-dyn", "dyn")
    print("DYN:", txt("#dyn-out", page))
    click("#btn-custom", "custom")
    print("CUSTOM:", txt("#custom-out", page))
    click("#btn-fields", "fields")
    print("FIELDS:", txt("#fields-out", page))

    click("#btn-noeager", "no-eager", 2500)
    print("books after no-eager:", txt("#books", page)[:400])
    names_noeager = page.eval_on_selector_all(".author-name", "els => els.map(e => e.textContent)")
    print("AUTHOR_NAMES_NOEAGER:", names_noeager)
    page.screenshot(path=f"{SHOTS}/{TAG}_04_noeager.png", full_page=True)

    click("#btn-bg", "bg load", 3000)
    print("BG:", txt("#bg-out", page))
    names_bg = page.eval_on_selector_all(".author-name", "els => els.map(e => e.textContent)")
    print("AUTHOR_NAMES_BG:", names_bg)

    click("#btn-chain", "chain", 3500)
    print("after chain, count:", txt("#count", page), "| authors:", txt("#authors", page)[:200])
    print("modules now:", txt("#mods-now", page))
    page.screenshot(path=f"{SHOTS}/{TAG}_05_chain.png", full_page=True)

    # reload -> on_load path again
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(2000)
    print("after reload modules-now:", txt("#mods-now", page))

    ctx2 = b.new_context()
    p2 = ctx2.new_page()
    p2.goto(URL, wait_until="networkidle", timeout=60000)
    p2.wait_for_timeout(1200)
    p2.click("#btn-sync"); p2.wait_for_timeout(2500)
    print("SECOND TAB author names:", p2.eval_on_selector_all(".author-name", "els => els.map(e => e.textContent)"))
    p2.screenshot(path=f"{SHOTS}/{TAG}_06_tab2.png", full_page=True)
    ctx2.close()

    b.close()

print("\n=== CONSOLE (errors/warnings) ===")
for m in console_msgs:
    if m["type"] in ("error", "warning"):
        print(m)
print("=== PAGE ERRORS ===", json.dumps(page_errors, indent=1))
print("=== BAD RESPONSES ===", json.dumps(bad_responses, indent=1))
print("=== WS frames containing 'author' (first 3) ===")
n = 0
for d, f in ws_frames:
    if "Le Guin" in f or "author" in f.lower():
        print(f[:1500]); n += 1
        if n >= 3: break
print("TOTAL_CONSOLE:", len(console_msgs), "TOTAL_WS:", len(ws_frames))
