"""Minimal repro driver: compile-time HTTPCookie.sync() 404s until a
server-side sync registers the route in the dev worker."""

import json
import sys

from playwright.sync_api import sync_playwright

FP, BP, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
base = f"http://localhost:{FP}"
res = {"steps": [], "console": [], "sync_responses": []}


def rec(r):
    if "cookies/sync" in r.url:
        res["sync_responses"].append({"url": r.url, "status": r.status})


with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = br.new_context().new_page()
    page.on("console", lambda m: res["console"].append({"type": m.type, "text": m.text[:250]}))
    page.on("response", rec)
    page.goto(base, wait_until="networkidle")
    page.wait_for_timeout(1500)

    n = len(res["sync_responses"])
    page.click("#sync")
    page.wait_for_timeout(2500)
    res["steps"].append({"step": "sync_click_cold", "responses": res["sync_responses"][n:]})
    page.screenshot(path=f"{OUT}/min_01_cold_sync.png")

    n = len(res["sync_responses"])
    page.click("#setcookie")  # server-side HTTPCookie set -> notify_sync -> sync()
    page.wait_for_timeout(3000)
    res["steps"].append({"step": "set_cookie_serverside", "note": page.inner_text("#note"),
                         "responses": res["sync_responses"][n:]})
    page.screenshot(path=f"{OUT}/min_02_after_set.png")

    n = len(res["sync_responses"])
    page.click("#sync")
    page.wait_for_timeout(2500)
    res["steps"].append({"step": "sync_click_warm", "responses": res["sync_responses"][n:]})

    res["cookies"] = [c["name"] for c in page.context.cookies()]
    br.close()

for s in res["steps"]:
    print(s, flush=True)
print("cookies:", res["cookies"])
print("console errors:", [c for c in res["console"] if c["type"] == "error"][:5])
with open(f"{OUT}/cookiemin.json", "w") as f:
    json.dump(res, f, indent=1)
