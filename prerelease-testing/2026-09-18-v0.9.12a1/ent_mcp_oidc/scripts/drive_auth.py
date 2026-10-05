"""Drive the OIDC auth app end-to-end in a real browser against the fake IdP.

Usage: python drive_auth.py <frontend_port> <label>
"""

import json
import sys
import time

import httpx
from playwright.sync_api import sync_playwright

PORT = int(sys.argv[1])
LABEL = sys.argv[2] if len(sys.argv) > 2 else "run"
BASE = f"http://localhost:{PORT}"
IDP = "http://localhost:9899"
OUT = {"label": LABEL, "steps": [], "console": [], "pageerrors": [], "failed_requests": [], "http_errors": []}


def step(name, **kw):
    """Record a step."""
    OUT["steps"].append({"step": name, **kw})
    print(f"[{name}] " + json.dumps(kw, default=str)[:400], flush=True)


def txt(page, sel, timeout=5000):
    """Read an element's text, '<absent>' if missing."""
    try:
        return page.locator(sel).first.inner_text(timeout=timeout)
    except Exception as e:  # noqa: BLE001
        return f"<absent:{type(e).__name__}>"


with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
    ctx = br.new_context()
    page = ctx.new_page()
    page.on("console", lambda m: OUT["console"].append({"type": m.type, "text": m.text[:400]}))
    page.on("pageerror", lambda e: OUT["pageerrors"].append(str(e)[:400]))
    page.on("requestfailed", lambda r: OUT["failed_requests"].append({"url": r.url[:200], "err": str(r.failure)[:200]}))
    page.on("response", lambda r: OUT["http_errors"].append({"url": r.url[:200], "status": r.status})
            if r.status >= 400 else None)

    def home():
        """Return to the public index (guards may have redirected us away)."""
        if not page.url.rstrip("/").endswith(str(PORT)):
            page.goto(f"{BASE}/", wait_until="networkidle")
            page.wait_for_timeout(1200)

    def snap(name):
        """Capture every probe on the index page."""
        step(name, hits=txt(page, "#hits", 3000), email=txt(page, "#email", 3000),
             provider=txt(page, "#provider", 3000), memo=txt(page, "#memo-user", 3000),
             secret_label=txt(page, "#secret-label", 3000),
             shared_label=txt(page, "#shared-label", 3000),
             note_echo=txt(page, "#note-echo", 3000),
             secret_note_raw=txt(page, "#secret-note-raw", 3000),
             cs=txt(page, "#cs-clicks", 3000), url=page.url)

    # 1. anonymous landing
    page.goto(f"{BASE}/", wait_until="networkidle")
    page.wait_for_timeout(1800)
    snap("anon_index")

    # raw server HTML: what is baked into the prerender before hydrate
    raw = httpx.get(f"{BASE}/", timeout=15).text
    step("anon_raw_html", has_top_secret="top-secret" in raw,
         has_default_shared="default-shared" in raw, length=len(raw))

    # 2. public handler works while anonymous
    page.click("#bump")
    page.wait_for_timeout(900)
    page.click("#cs-click")
    page.wait_for_timeout(900)
    snap("anon_public_events")

    # 2b. LEAK PROBE: public handler mutates server-side data read by a PROTECTED var
    page.click("#poison-shared")
    page.wait_for_timeout(1500)
    snap("anon_after_poison_shared")

    # 2c. LEAK PROBE: public handler writes the PROTECTED field
    page.click("#poison-field")
    page.wait_for_timeout(1500)
    snap("anon_after_poison_field")

    # 3. protected handler while anonymous
    page.click("#set-secret")
    page.wait_for_timeout(1500)
    step("anon_protected_event", url=page.url)
    home()

    page.click("#slow-secret")
    page.wait_for_timeout(1800)
    step("anon_protected_bg_event", url=page.url)
    home()

    # 4. protected page while anonymous
    page.goto(f"{BASE}/secret", wait_until="networkidle")
    page.wait_for_timeout(2200)
    step("anon_secret_page", url=page.url, heading=txt(page, "#secret-heading", 2000),
         body=page.locator("body").inner_text()[:250])

    # 5. login
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.wait_for_timeout(2000)
    step("login_page", url=page.url, body=page.locator("body").inner_text()[:300])
    btns = page.locator("button, a").all_inner_texts()
    step("login_buttons", buttons=btns[:15])
    clicked = False
    for name in ("generic", "Generic", "Sign in", "Login", "Log in", "Continue"):
        loc = page.get_by_text(name, exact=False)
        if loc.count():
            loc.first.click()
            clicked = True
            step("clicked_provider", label=name)
            break
    if not clicked and page.locator("button").count():
        page.locator("button").first.click()
        clicked = True
        step("clicked_provider", label="<first button>")
    page.wait_for_timeout(4000)
    step("after_login_click", url=page.url, body=page.locator("body").inner_text()[:300])

    # 6. back at index authenticated?
    page.goto(f"{BASE}/", wait_until="networkidle")
    page.wait_for_timeout(2500)
    snap("post_login_index")

    # 7. protected event now
    page.click("#set-secret")
    page.wait_for_timeout(1200)
    snap("auth_protected_event")
    page.click("#slow-secret")
    page.wait_for_timeout(1500)
    snap("auth_protected_bg_event")

    # 8. protected page now
    page.goto(f"{BASE}/secret", wait_until="networkidle")
    page.wait_for_timeout(2000)
    step("auth_secret_page", url=page.url, heading=txt(page, "#secret-heading", 3000),
         email=txt(page, "#secret-email"), secret_label=txt(page, "#secret-label-2"))

    # 9. reload persistence (cookie-backed session)
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(2000)
    step("auth_reload", url=page.url, email=txt(page, "#secret-email"))

    # 10. new tab in same context shares the session
    p2 = ctx.new_page()
    p2.goto(f"{BASE}/secret", wait_until="networkidle")
    p2.wait_for_timeout(2000)
    step("auth_second_tab", url=p2.url, email=txt(p2, "#secret-email"))
    p2.close()

    # 11. logout
    page.goto(f"{BASE}/logout", wait_until="networkidle")
    page.wait_for_timeout(3500)
    step("after_logout", url=page.url, body=page.locator("body").inner_text()[:250])
    page.goto(f"{BASE}/", wait_until="networkidle")
    page.wait_for_timeout(2000)
    snap("post_logout_index")
    page.goto(f"{BASE}/secret", wait_until="networkidle")
    page.wait_for_timeout(2000)
    step("post_logout_secret", url=page.url, heading=txt(page, "#secret-heading", 2000))

    ctx.close()
    br.close()

OUT["idp_log"] = httpx.get(f"{IDP}/_log", timeout=10).json()["log"]
path = f"/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad/apps/ent_mcp_oidc/logs/auth_{LABEL}.json"
with open(path, "w") as f:
    json.dump(OUT, f, indent=1)
print("\nCONSOLE ERRORS:", json.dumps([c for c in OUT["console"] if c["type"] == "error"], indent=1)[:1500])
print("PAGE ERRORS:", json.dumps(OUT["pageerrors"], indent=1)[:1200])
print("FAILED REQ:", json.dumps(OUT["failed_requests"], indent=1)[:800])
print("HTTP >=400:", json.dumps(OUT["http_errors"], indent=1)[:1500])
print("IDP LOG:", json.dumps(OUT["idp_log"], indent=1)[:2500])
print("saved", path)
