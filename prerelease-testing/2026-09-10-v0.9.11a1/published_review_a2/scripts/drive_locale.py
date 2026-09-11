"""Drive the locale-isolation matrix and record every moment's text.

Usage: drive_locale.py <base_url> <out.json>
"""

import json
import sys

from playwright.sync_api import sync_playwright

BASE, OUT = sys.argv[1], sys.argv[2]
R = {"base": BASE, "routes": {}, "console": [], "pageerrors": [], "failed": [], "http_errors": [],
     "locale_requests": []}

IDS = {
    "/": ["home-french", "home-plain", "home-fromnow", "home-tonow", "home-title", "home-duration"],
    "/reverse": ["rev-plain", "rev-fromnow", "rev-tonow", "rev-title", "rev-duration", "rev-french"],
    "/english": ["eng-plain", "eng-fromnow", "eng-tonow", "eng-title", "eng-duration"],
    "/en": ["en-explicit", "en-plain", "en-fromnow", "en-tonow", "en-title", "en-duration"],
    "/reactive": ["react-var", "react-plain", "react-fromnow", "react-tonow", "react-title", "react-duration"],
}


def read(page, ids):
    """Text of each id, plus the title attribute where present."""
    out = {}
    for i in ids:
        try:
            out[i] = page.locator(f"#{i}").first.inner_text(timeout=5000)
        except Exception as e:  # noqa: BLE001
            out[i] = f"<absent:{type(e).__name__}>"
    try:
        out["_title_attr"] = page.locator("[id$='-title']").first.get_attribute("title")
    except Exception:  # noqa: BLE001
        out["_title_attr"] = None
    return out


def visit(page, route, label):
    """Navigate to a route and record it."""
    print(f"  -> visiting {route}", flush=True)
    page.goto(BASE + route, wait_until="domcontentloaded")
    try:
        page.wait_for_selector("#ready", timeout=45000, state="attached")
    except Exception as e:  # noqa: BLE001
        R["routes"][label] = {"_ROUTE_FAILED": f"{type(e).__name__}",
                              "_body": page.locator("body").inner_text()[:200]}
        print(f"[{label}] ROUTE FAILED TO RENDER", flush=True)
        return
    page.wait_for_timeout(2500)
    R["routes"][label] = read(page, IDS[route])
    print(f"[{label}] " + json.dumps(R['routes'][label])[:300], flush=True)


with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
    page = br.new_context().new_page()
    page.on("console", lambda m: R["console"].append({"type": m.type, "text": m.text[:250]}))
    page.on("pageerror", lambda e: R["pageerrors"].append(str(e)[:250]))
    page.on("requestfailed", lambda r: R["failed"].append({"url": r.url[:200], "err": str(r.failure)[:120]}))
    page.on("response", lambda r: (
        R["http_errors"].append({"url": r.url[:200], "status": r.status}) if r.status >= 400 else None))
    page.on("request", lambda r: (
        R["locale_requests"].append({"url": r.url[:200]})
        if ("moment" in r.url and "locale" in r.url) else None))

    visit(page, "/", "1_home_french_first")
    visit(page, "/reverse", "2_reverse_french_last")
    visit(page, "/english", "3_english_only")
    if "5494" not in BASE:
        visit(page, "/en", "4_explicit_en")

    # client-side navigation away and back
    page.goto(BASE + "/", wait_until="networkidle")
    page.wait_for_selector("#ready", timeout=60000, state="attached")
    page.wait_for_timeout(2000)
    page.click("#nav-english")
    page.wait_for_selector("#ready", timeout=60000, state="attached")
    page.wait_for_timeout(2500)
    R["routes"]["5_english_after_client_nav_from_french"] = read(page, IDS["/english"])
    print("[5_english_after_client_nav_from_french] " + json.dumps(R["routes"]["5_english_after_client_nav_from_french"])[:300], flush=True)

    page.click("#nav-home")
    page.wait_for_selector("#ready", timeout=60000, state="attached")
    page.wait_for_timeout(2000)
    page.click("#nav-english")
    page.wait_for_selector("#ready", timeout=60000, state="attached")
    page.wait_for_timeout(2000)
    page.reload(wait_until="networkidle")
    page.wait_for_selector("#ready", timeout=60000, state="attached")
    page.wait_for_timeout(2500)
    R["routes"]["6_english_after_reload"] = read(page, IDS["/english"])
    print("[6_english_after_reload] " + json.dumps(R["routes"]["6_english_after_reload"])[:300], flush=True)

    # reactive locale switching
    page.goto(BASE + "/reactive", wait_until="networkidle")
    page.wait_for_selector("#ready", timeout=60000, state="attached")
    page.wait_for_timeout(2500)
    R["routes"]["7_reactive_initial_fr"] = read(page, IDS["/reactive"])
    for btn, label in (("#btn-en", "8_reactive_en"), ("#btn-empty", "9_reactive_empty"), ("#btn-fr", "10_reactive_fr_again")):
        page.click(btn)
        page.wait_for_timeout(2000)
        R["routes"][label] = read(page, IDS["/reactive"])
        print(f"[{label}] " + json.dumps(R['routes'][label])[:300], flush=True)

    # after the reactive route touched fr+en, does a fresh english route stay English?
    page.click("#nav-english")
    page.wait_for_selector("#ready", timeout=60000, state="attached")
    page.wait_for_timeout(2500)
    R["routes"]["11_english_after_reactive"] = read(page, IDS["/english"])
    print("[11_english_after_reactive] " + json.dumps(R["routes"]["11_english_after_reactive"])[:300], flush=True)

    R["console_errors"] = [c for c in R["console"] if c["type"] == "error"]
    R["defineLocale_warnings"] = [c for c in R["console"] if "defineLocale" in c["text"]]
    br.close()

with open(OUT, "w") as f:
    json.dump(R, f, indent=1)
print("\nlocale module requests:", json.dumps(R["locale_requests"])[:400])
print("console errors:", json.dumps(R["console_errors"])[:400])
print("defineLocale warnings:", len(R["defineLocale_warnings"]))
print("failed requests:", json.dumps(R["failed"])[:300])
print("http>=400:", json.dumps(R["http_errors"])[:300])
print("saved", OUT)
