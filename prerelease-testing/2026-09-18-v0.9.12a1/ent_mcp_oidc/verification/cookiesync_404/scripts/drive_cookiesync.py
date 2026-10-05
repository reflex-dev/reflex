"""Drive the shipped OIDC demo: Cookie Sync before login, login, Cookie Sync after."""

import json
import sys
import time

from playwright.sync_api import sync_playwright

FP, BP, LABEL, OUT = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
base = f"http://localhost:{FP}"
sync_url = f"http://localhost:{BP}/_reflex/cookies/sync"

res = {"label": LABEL, "steps": [], "console": [], "responses": []}


def step(name, **kw):
    res["steps"].append({"step": name, **kw})
    print(name, kw, flush=True)


with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = br.new_context()
    page = ctx.new_page()
    page.on("console", lambda m: res["console"].append({"type": m.type, "text": m.text[:300]}))
    page.on(
        "response",
        lambda r: res["responses"].append({"url": r.url, "status": r.status})
        if "cookies/sync" in r.url
        else None,
    )
    page.goto(base, wait_until="networkidle")
    page.wait_for_timeout(2000)
    page.screenshot(path=f"{OUT}/{LABEL}_01_index.png")
    step("loaded", title=page.title())

    # 1. cookie sync BEFORE any login
    page.get_by_role("button", name="Cookie Sync").click()
    page.wait_for_timeout(2500)
    before = [r for r in res["responses"] if "cookies/sync" in r["url"]]
    step("sync_before_login", responses=list(before))
    page.screenshot(path=f"{OUT}/{LABEL}_02_after_sync_click.png")

    # 2. login with Okta
    n_before = len(res["responses"])
    page.get_by_role("button", name="Login with Okta").click()
    page.wait_for_timeout(6000)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(3000)
    logged_in = page.get_by_role("button", name="Log AT").count() > 0
    step("login", logged_in=logged_in, url=page.url,
         sync_during_login=res["responses"][n_before:])
    page.screenshot(path=f"{OUT}/{LABEL}_03_logged_in.png")

    # 3. cookie sync AFTER login
    n2 = len(res["responses"])
    if logged_in:
        page.get_by_role("button", name="Cookie Sync").click()
        page.wait_for_timeout(2500)
    step("sync_after_login", responses=res["responses"][n2:])
    page.screenshot(path=f"{OUT}/{LABEL}_04_after_sync2.png")

    res["end"] = time.time()
    br.close()

with open(f"{OUT}/{LABEL}_cookiesync.json", "w") as f:
    json.dump(res, f, indent=1)
print("WROTE", f"{OUT}/{LABEL}_cookiesync.json")
