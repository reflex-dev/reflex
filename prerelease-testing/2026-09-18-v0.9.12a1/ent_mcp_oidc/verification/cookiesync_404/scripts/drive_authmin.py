"""AuthPlugin control: is /_reflex/cookies/sync live from startup?"""
import json, sys
from playwright.sync_api import sync_playwright

FP, OUT = sys.argv[1], sys.argv[2]
res = {"sync": [], "console": []}
with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = br.new_context().new_page()
    page.on("response", lambda r: res["sync"].append({"url": r.url, "status": r.status}) if "cookies/sync" in r.url else None)
    page.on("console", lambda m: res["console"].append(f"{m.type}: {m.text[:200]}"))
    page.goto(f"http://localhost:{FP}/", wait_until="networkidle")
    page.wait_for_timeout(2500)
    res["after_load"] = list(res["sync"])
    n = len(res["sync"]); page.click("#sync"); page.wait_for_timeout(2500)
    res["after_sync_click"] = res["sync"][n:]
    n = len(res["sync"]); page.click("#bump"); page.wait_for_timeout(2000)
    res["after_bump"] = res["sync"][n:]
    n = len(res["sync"]); page.click("#sync"); page.wait_for_timeout(2500)
    res["after_sync_click2"] = res["sync"][n:]
    br.close()
print(json.dumps({k: v for k, v in res.items() if k != "sync"}, indent=1))
json.dump(res, open(f"{OUT}/authmin.json", "w"), indent=1)
