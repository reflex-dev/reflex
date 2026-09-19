"""Iframed login *and* logout popup flow of the shipped demos/oidc app.

Logs in through the popup from inside the /iframe page, then logs out the same
way, recording each popup's URL trail, whether it closed, and the state of the
iframed app afterwards.

Usage: python drive_popup_logout.py <frontend_port> <label> <shotdir>
"""

import json
import sys

from playwright.sync_api import sync_playwright

FPORT, LABEL, SHOTS = int(sys.argv[1]), sys.argv[2], sys.argv[3]
BASE = f"http://localhost:{FPORT}"
OUT = {"label": LABEL, "steps": [], "popups": [], "console": [], "pageerrors": []}


def step(name, **kw):
    """Record and print one step."""
    OUT["steps"].append({"step": name, **kw})
    print(f"[{name}] " + json.dumps(kw, default=str)[:500], flush=True)


with sync_playwright() as p:
    br = p.chromium.launch(
        executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"]
    )
    ctx = br.new_context(viewport={"width": 1400, "height": 950})
    page = ctx.new_page()
    page.on("console",
            lambda m: OUT["console"].append({"type": m.type, "text": m.text[:250]}))
    page.on("pageerror", lambda e: OUT["pageerrors"].append(str(e)[:250]))

    popups = []

    def on_popup(pg):
        """Track every popup window the app opens."""
        rec = {"opened_at": len(OUT["steps"]), "urls": [pg.url]}
        popups.append((pg, rec))
        OUT["popups"].append(rec)
        pg.on("framenavigated",
              lambda f: rec["urls"].append(f.url) if f == pg.main_frame else None)

    ctx.on("page", on_popup)

    def inner():
        """The iframed app frame."""
        frames = [f for f in page.frames if f != page.main_frame]
        return frames[0] if frames else None

    def inner_text():
        """Text of the iframed app."""
        fr = inner()
        if fr is None:
            return "<no frame>"
        try:
            return fr.locator("body").inner_text(timeout=6000)
        except Exception as e:  # noqa: BLE001
            return f"<absent:{type(e).__name__}>"

    page.goto(f"{BASE}/iframe", wait_until="networkidle")
    page.wait_for_timeout(3000)
    step("start", inner=inner_text()[:150])

    inner().get_by_role("button", name="Login with Okta").click()
    page.wait_for_timeout(12000)
    step("after_login",
         logged_in="alice@example.test" in inner_text(),
         popups=[{"urls": [u[:90] for u in r["urls"]], "closed": pg.is_closed()}
                 for pg, r in popups])
    page.screenshot(path=f"{SHOTS}/{LABEL}_40_iframe_logged_in.png", full_page=True)

    n_before = len(popups)
    lo = inner().get_by_role("button", name="Logout")
    step("logout_button", count=lo.count())
    if lo.count():
        lo.first.click()
        page.wait_for_timeout(12000)
    step("after_logout",
         logged_out="Login with Okta" in inner_text(),
         inner=inner_text()[:200],
         new_popups=[{"urls": [u[:90] for u in r["urls"]], "closed": pg.is_closed()}
                     for pg, r in popups[n_before:]],
         all_popups_closed=all(pg.is_closed() for pg, _ in popups))
    page.screenshot(path=f"{SHOTS}/{LABEL}_41_iframe_logged_out.png", full_page=True)

    br.close()

with open(f"{SHOTS}/popup_logout_{LABEL}.json", "w") as fh:
    json.dump(OUT, fh, indent=1)
print("console errors:", [c for c in OUT["console"] if c["type"] == "error"][:5])
print("page errors:", OUT["pageerrors"][:3])
