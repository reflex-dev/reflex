import sys, time, json
from playwright.sync_api import sync_playwright

URL = sys.argv[1]
N = int(sys.argv[2]) if len(sys.argv) > 2 else 20
SHOTS = sys.argv[3]

errors, console_errors, bad = [], [], []
results = []
t0 = time.time()
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctxs, pages = [], []
    for i in range(N):
        c = b.new_context()
        pg = c.new_page()
        pg.on("pageerror", lambda e, i=i: errors.append(f"ctx{i}: {str(e)[:200]}"))
        pg.on("console", lambda m, i=i: console_errors.append(f"ctx{i}: {m.text[:200]}") if m.type == "error" else None)
        pg.on("response", lambda r, i=i: bad.append(f"ctx{i}: {r.status} {r.url[:100]}") if r.status >= 400 else None)
        ctxs.append(c); pages.append(pg)
    # navigate all
    for i, pg in enumerate(pages):
        try:
            pg.goto(URL, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            errors.append(f"ctx{i} goto: {type(e).__name__}: {e}")
    print(f"navigated {N} contexts in {time.time()-t0:.1f}s")
    # fire DB reads as close to simultaneously as possible
    for i, pg in enumerate(pages):
        try:
            pg.click("#btn-seed", timeout=20000)
        except Exception as e:
            errors.append(f"ctx{i} seed: {type(e).__name__}: {str(e)[:120]}")
    for i, pg in enumerate(pages):
        try:
            pg.click("#btn-sync", timeout=20000, no_wait_after=True)
        except Exception as e:
            errors.append(f"ctx{i} sync-click: {type(e).__name__}: {str(e)[:120]}")
    for i, pg in enumerate(pages):
        try:
            pg.click("#btn-bg", timeout=20000, no_wait_after=True)
        except Exception as e:
            errors.append(f"ctx{i} bg-click: {type(e).__name__}: {str(e)[:120]}")
    deadline = time.time() + 60
    for i, pg in enumerate(pages):
        try:
            pg.wait_for_function("document.querySelectorAll('.author-name').length >= 3", timeout=max(2000, int((deadline-time.time())*1000)))
            names = pg.eval_on_selector_all(".author-name", "els => els.map(e=>e.textContent)")
            bg = pg.inner_text("#bg-out", timeout=5000)
            results.append({"ctx": i, "names": names, "bg": bg[:80]})
        except Exception as e:
            results.append({"ctx": i, "ERROR": f"{type(e).__name__}: {str(e)[:150]}"})
    pages[0].screenshot(path=f"{SHOTS}/prod_fork_ctx0.png", full_page=True)
    for c in ctxs: c.close()
    b.close()

ok = [r for r in results if "names" in r and len(r["names"]) == 3 and all(r["names"])]
bad_r = [r for r in results if r not in ok]
print(f"ELAPSED {time.time()-t0:.1f}s | OK contexts: {len(ok)}/{N}")
print("SAMPLE OK:", json.dumps(ok[:2], indent=1))
print("NON-OK:", json.dumps(bad_r[:6], indent=1))
print("PAGE ERRORS:", json.dumps(errors[:10], indent=1))
print("CONSOLE ERRORS:", json.dumps(console_errors[:10], indent=1))
print("BAD RESPONSES:", json.dumps(bad[:10], indent=1))
