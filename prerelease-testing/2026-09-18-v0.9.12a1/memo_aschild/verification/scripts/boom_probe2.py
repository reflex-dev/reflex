"""Check whether a crash in the UNTAKEN rx.cond branch reaches the browser."""
import sys
from playwright.sync_api import sync_playwright

BASE = sys.argv[1]
OUT = sys.argv[2]
lines = []


def p(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    lines.append(s)


with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    for route in ("/boomvar", "/boommemo", "/boomnull"):
        page = ctx.new_page()
        msgs = []
        page.on("console", lambda m: msgs.append(f"[{m.type}] {m.text[:200]}"))
        page.on("pageerror", lambda e: msgs.append(f"[pageerror] {str(e)[:200]}"))
        page.goto(f"{BASE}{route}", wait_until="networkidle")
        page.wait_for_timeout(2500)
        body = page.inner_text("body")[:300].replace("\n", " | ")
        ok = page.locator("#ok_text").count()
        p(f"ROUTE {route}: #ok_text count={ok}")
        p(f"  body: {body}")
        errs = [m for m in msgs if "pageerror" in m or "[error]" in m]
        p(f"  errors({len(errs)}): " + " || ".join(e[:180] for e in errs[:4]))
        page.screenshot(path=f"{OUT}/{route.strip('/')}.png")
        page.close()
    ctx.close()
    b.close()

open(f"{OUT}/boom_probe2.log", "w").write("\n".join(lines) + "\n")
