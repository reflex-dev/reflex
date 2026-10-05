import json, sys, time
from playwright.sync_api import sync_playwright

url, outp = sys.argv[1], sys.argv[2]
res = {"console": [], "page_errors": [], "failed": [], "bad_status": [], "steps": []}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
                          args=["--no-sandbox"])
    pg = b.new_page()
    pg.on("console", lambda m: res["console"].append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
    pg.on("pageerror", lambda e: res["page_errors"].append(str(e)))
    pg.on("requestfailed", lambda r: res["failed"].append(f"{r.url} {r.failure}"))
    pg.on("response", lambda r: res["bad_status"].append(f"{r.status} {r.url}") if r.status >= 400 else None)
    pg.goto(url, wait_until="networkidle")
    time.sleep(2)

    def snap(label):
        res["steps"].append({"step": label,
                             "secret": pg.inner_text("#secret"),
                             "n": pg.inner_text("#n")})
    snap("after_load_hidden")
    for i in range(2):
        pg.click("#bump"); time.sleep(1)
    snap("after_2_bumps_hidden")
    pg.click("#show"); time.sleep(1.5)
    snap("after_show")
    pg.click("#bump"); time.sleep(1)
    snap("after_bump_visible")
    b.close()
json.dump(res, open(outp, "w"), indent=2)
print(json.dumps(res, indent=2))
