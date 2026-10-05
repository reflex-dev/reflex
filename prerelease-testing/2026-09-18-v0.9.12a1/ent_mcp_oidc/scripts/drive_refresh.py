"""Watch the proactive access-token refresh of the shipped demos/oidc app.

Logs in with Databricks (the provider that requests ``offline_access`` and
overrides ``_on_access_token_change``), then keeps the page open and samples
the two access-token-hash badges plus any toast until the refresh fires.

Usage: python drive_refresh.py <frontend_port> <idp_port> <label> <shotdir> <seconds>
"""

import json
import sys
import time

import httpx
from playwright.sync_api import sync_playwright

FPORT, IDPPORT = int(sys.argv[1]), int(sys.argv[2])
LABEL, SHOTS = sys.argv[3], sys.argv[4]
BUDGET = int(sys.argv[5]) if len(sys.argv) > 5 else 200
BASE = f"http://localhost:{FPORT}"
IDP = f"http://localhost:{IDPPORT}"

OUT = {"label": LABEL, "samples": [], "toasts": [], "console": [], "pageerrors": []}


def idp_log():
    """Fetch the fake IdP's request log."""
    try:
        return httpx.get(f"{IDP}/_log", timeout=10).json()["log"]
    except Exception as e:  # noqa: BLE001
        return [f"<idp log error {e}>"]


with sync_playwright() as p:
    br = p.chromium.launch(
        executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"]
    )
    ctx = br.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    page.on(
        "console",
        lambda m: OUT["console"].append({"type": m.type, "text": m.text[:250]}),
    )
    page.on("pageerror", lambda e: OUT["pageerrors"].append(str(e)[:250]))

    page.goto(f"{BASE}/", wait_until="networkidle")
    page.wait_for_timeout(2500)
    page.get_by_role("button", name="Login with Databricks").click()
    page.wait_for_timeout(6000)
    body = page.locator("body").inner_text(timeout=8000)
    print("logged in:", "alice@example.test" in body, flush=True)
    page.screenshot(path=f"{SHOTS}/{LABEL}_20_dbx_login.png", full_page=True)

    start = time.time()
    seen_hashes = []
    while time.time() - start < BUDGET:
        page.wait_for_timeout(5000)
        try:
            body = page.locator("body").inner_text(timeout=8000)
        except Exception as e:  # noqa: BLE001
            body = f"<absent:{type(e).__name__}>"
        hashes = [w for w in body.split() if len(w) == 64 and all(
            c in "0123456789abcdef" for c in w)]
        toast = "Access token refreshed" in body
        if toast and not OUT["toasts"]:
            OUT["toasts"].append({"at": round(time.time() - start, 1)})
            page.screenshot(path=f"{SHOTS}/{LABEL}_21_refresh_toast.png",
                            full_page=True)
        sample = {
            "t": round(time.time() - start, 1),
            "hashes": sorted(set(hashes)),
            "toast": toast,
            "logged_in": "alice@example.test" in body,
        }
        OUT["samples"].append(sample)
        print(json.dumps(sample), flush=True)
        for h in hashes:
            if h not in seen_hashes:
                seen_hashes.append(h)
        if len(seen_hashes) >= 2 and OUT["toasts"]:
            print("refresh observed, stopping early", flush=True)
            break

    OUT["distinct_hashes"] = seen_hashes
    OUT["idp_log"] = idp_log()
    page.screenshot(path=f"{SHOTS}/{LABEL}_22_end.png", full_page=True)
    br.close()

with open(f"{SHOTS}/refresh_{LABEL}.json", "w") as fh:
    json.dump(OUT, fh, indent=1)
print("\ndistinct access-token hashes seen:", len(OUT["distinct_hashes"]))
print("refresh grants at IdP:",
      sum(1 for line in OUT["idp_log"] if "REFRESH OK" in line))
print("console errors:", [c for c in OUT["console"] if c["type"] == "error"][:6])
print("page errors:", OUT["pageerrors"][:4])
