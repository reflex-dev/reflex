"""Count rendered svgs for the Var-tag digit icons. Usage: drive_icons.py http://localhost:3300 shot.png"""
import json, sys, time
from playwright.sync_api import sync_playwright
base = sys.argv[1].rstrip("/")
out = {"console": []}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    pg.on("console", lambda m: out["console"].append(f"{m.type}: {m.text[:160]}") if m.type in ("error", "warning") else None)
    pg.goto(base + "/"); pg.wait_for_selector("#h", timeout=60000); time.sleep(3)
    cnt = lambda sel: pg.locator(f"{sel} svg").count()  # noqa: E731
    out["var_icon_svgs"] = cnt("#var-icon")
    out["static_icon_svgs"] = cnt("#static-icon")
    out["foreach_svgs"] = [(e.inner_text(), e.locator("svg").count()) for e in pg.locator(".fe-icon").all()]
    pg.click("#flip"); time.sleep(2)
    out["var_icon_svgs_after_flip"] = cnt("#var-icon")
    out["var_icon_class_after_flip"] = pg.eval_on_selector("#var-icon svg", "e => e.getAttribute('class')") if cnt("#var-icon") else None
    pg.screenshot(path=sys.argv[2])
    b.close()
out["console_count"] = len(out["console"]); out["console"] = sorted(set(out["console"]))[:5]
print(json.dumps(out, indent=1))
