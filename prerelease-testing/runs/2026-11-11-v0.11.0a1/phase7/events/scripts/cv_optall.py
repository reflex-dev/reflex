"""Drive /optall: read ops when None, after fill, after clear; report console / failed requests. usage: cv_optall.py <base> <png_prefix>"""
import sys

from playwright.sync_api import sync_playwright

base, prefix = sys.argv[1], sys.argv[2]
IDS = ["s_contains", "s_len", "s_union_len", "s_inter_len", "l_contains", "l_len", "l_join", "l_rev", "l_gt0", "t_len"]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    msgs = []
    pg.on("console", lambda m: msgs.append(f"console.{m.type}: {m.text[:250]}") if m.type in ("error", "warning") else None)
    pg.on("pageerror", lambda e: msgs.append(f"pageerror: {str(e)[:250]}"))
    pg.on("response", lambda r: msgs.append(f"HTTP {r.status} {r.url}") if r.status >= 400 else None)
    pg.goto(base + "/optall")
    pg.wait_for_timeout(6000)

    def snap(label):
        if not pg.query_selector("#hdr"):
            print(label, "PAGE BROKEN:", pg.inner_text("body")[:300].replace("\n", " | "))
            return
        vals = {i: pg.inner_text(f"#{i}").split("=", 1)[1] for i in IDS}
        print(label, vals, "items=", [e.inner_text() for e in pg.query_selector_all(".item")])

    snap("none ")
    pg.screenshot(path=f"{prefix}_none.png")
    for btn in ("fill", "clear"):
        if pg.query_selector(f"#{btn}"):
            pg.click(f"#{btn}")
            pg.wait_for_timeout(1500)
            snap(f"{btn:5s}")
    pg.screenshot(path=f"{prefix}_end.png")
    for m in msgs:
        if "favicon" not in m:
            print("   ", m)
    b.close()
