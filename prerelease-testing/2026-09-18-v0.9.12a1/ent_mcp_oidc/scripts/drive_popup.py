"""Exercise the iframed popup login flow of the shipped demos/oidc app.

The demo's /iframe page embeds the app; inside an iframe reflex-enterprise
switches to the popup login flow (``_use_popup_flow`` -> ``is_iframed``).
This records what the popup window does after the IdP callback: which URLs it
visits, whether it closes itself, and whether the opener ends up signed in.

Usage: python drive_popup.py <frontend_port> <label> <shotdir>
"""

import json
import sys

from playwright.sync_api import sync_playwright

FPORT = int(sys.argv[1])
LABEL = sys.argv[2]
SHOTS = sys.argv[3]
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
    page.on(
        "console",
        lambda m: OUT["console"].append({"type": m.type, "text": m.text[:250]}),
    )
    page.on("pageerror", lambda e: OUT["pageerrors"].append(str(e)[:250]))

    popups = []

    def on_popup(pg):
        """Track every popup window the app opens."""
        rec = {"urls": [pg.url], "closed": None, "size": None}
        popups.append((pg, rec))
        OUT["popups"].append(rec)
        pg.on("framenavigated", lambda f: rec["urls"].append(f.url)
              if f == pg.main_frame else None)
        pg.on("close", lambda _: rec.update(closed=True))

    ctx.on("page", on_popup)

    page.goto(f"{BASE}/iframe", wait_until="networkidle")
    page.wait_for_timeout(3000)
    inner = [f for f in page.frames if f != page.main_frame]
    step("iframe_loaded", frames=[f.url for f in page.frames], inner=len(inner))
    page.screenshot(path=f"{SHOTS}/{LABEL}_10_iframe_anon.png", full_page=True)

    fr = inner[0]
    fr.get_by_role("button", name="Login with Okta").click()
    page.wait_for_timeout(8000)

    for pg, rec in popups:
        try:
            rec["closed"] = pg.is_closed()
            if not pg.is_closed():
                rec["urls"].append(pg.url)
                rec["title"] = pg.title()
                rec["body"] = pg.locator("body").inner_text(timeout=4000)[:400]
                rec["size"] = pg.viewport_size
                pg.screenshot(path=f"{SHOTS}/{LABEL}_11_popup_open.png")
        except Exception as e:  # noqa: BLE001
            rec["error"] = f"{type(e).__name__}: {e}"[:200]
    step("after_login_click", popups=OUT["popups"])

    # give the flow more time in case the close is delayed
    page.wait_for_timeout(6000)
    for pg, rec in popups:
        rec["closed_final"] = pg.is_closed()
        if not pg.is_closed():
            try:
                rec["url_final"] = pg.url
                rec["body_final"] = pg.locator("body").inner_text(timeout=4000)[:400]
            except Exception as e:  # noqa: BLE001
                rec["error_final"] = f"{type(e).__name__}: {e}"[:200]

    inner = [f for f in page.frames if f != page.main_frame]
    inner_text = ""
    if inner:
        try:
            inner_text = inner[0].locator("body").inner_text(timeout=5000)[:400]
        except Exception as e:  # noqa: BLE001
            inner_text = f"<absent:{type(e).__name__}>"
    step(
        "opener_state",
        popups=OUT["popups"],
        inner_logged_in="alice@example.test" in inner_text,
        inner_text=inner_text,
        outer_url=page.url,
    )
    page.screenshot(path=f"{SHOTS}/{LABEL}_12_iframe_after_login.png", full_page=True)

    br.close()

with open(f"{SHOTS}/popup_{LABEL}.json", "w") as fh:
    json.dump(OUT, fh, indent=1)
print("\nconsole errors:", [c for c in OUT["console"] if c["type"] == "error"][:5])
print("page errors:", OUT["pageerrors"][:5])
