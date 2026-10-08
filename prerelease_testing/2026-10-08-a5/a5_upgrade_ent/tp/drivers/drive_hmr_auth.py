"""Dev hot reload while logged in with reflex-local-auth: register + login, edit the app file (server restarts),
then check the browser tab recovers, is still authenticated and the server log has no traceback.

Usage: drive_hmr_auth.py <base_url> <app_file_to_touch> <server_log> <out_json>
"""
import json
import re
import sys
import time
from pathlib import Path

from tpdrive import Capture, browser, wait_text, wait_url

BASE, APPFILE, LOG, OUT = sys.argv[1].rstrip("/"), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
cap = Capture()
user = f"hmr{int(time.time()) % 100000}"
pw = "pw-123456"
log_before = len(LOG.read_text(errors="replace"))
with browser() as b:
    ctx = b.new_context()
    page = cap.attach(ctx.new_page(), "main")
    page.goto(BASE + "/need2login", wait_until="networkidle")
    wait_url(page, r"/login")
    page.get_by_role("link", name="Register").click()
    page.wait_for_selector("input#username")
    page.fill("input#username", user); page.fill("input#password", pw); page.fill("input#confirm_password", pw)
    page.get_by_role("button", name="Sign up").click()
    wait_text(page, "body", "Registration successful")
    wait_url(page, r"/login", 10)
    page.wait_for_selector("input#username")
    page.fill("input#username", user); page.fill("input#password", pw)
    try:
        page.get_by_role("button", name="Sign in").click(timeout=8000)
    except Exception:
        print("SIGN-IN BUTTON MISSING; url=", page.url, "body=", page.locator("body").inner_text()[:300].replace("\n", " | "))
        page.screenshot(path=OUT.replace(".json", "-fail.png"))
        raise
    cap.check("logged in (redirect_to /need2login)", "/need2login" in wait_url(page, r"/need2login"), page.url)
    page.goto(BASE + "/protected", wait_until="networkidle")
    cap.check("protected data before edit", f"private data for {user}" in wait_text(page, "body", f"private data for {user}"))
    # edit the app file (appends a comment) -> dev backend reload
    src = APPFILE.read_text()
    APPFILE.write_text(src + f"\n# hmr edit {time.time()}\n")
    t0 = time.time()
    recovered = None
    while time.time() - t0 < 90:
        page.wait_for_timeout(1000)
        try:
            if page.locator("body").inner_text(timeout=1000) and f"private data for {user}" in page.locator("body").inner_text(timeout=1000):
                # make sure it is a post-reload render: trigger an event that round-trips through the new backend
                pass
        except Exception:
            pass
        r = page.evaluate("() => fetch('/ping').then(r => r.status).catch(() => -1)") if False else None
        # poll the backend directly
        import urllib.request
        try:
            code = urllib.request.urlopen(BASE.replace(":3463", ":8463") + "/ping", timeout=2).status
        except Exception:
            code = -1
        if code == 200 and time.time() - t0 > 4:
            recovered = round(time.time() - t0, 1)
            break
    cap.check("backend answers /ping again after the edit", recovered is not None, f"after {recovered}s")
    page.wait_for_timeout(3000)
    page.reload(wait_until="networkidle")
    cap.check("still authenticated after backend reload (reload tab)", f"private data for {user}" in wait_text(page, "body", f"private data for {user}", timeout=20), page.locator("body").inner_text()[:150])
    page2 = cap.attach(ctx.new_page(), "tab2")
    page2.goto(BASE + "/user-info", wait_until="networkidle")
    cap.check("second tab sees the user", f"Username: {user}" in wait_text(page2, "body", f"Username: {user}", timeout=20))
    page.get_by_role("link", name="Logout").first.click()
    page.wait_for_timeout(1500)
    page.goto(BASE + "/protected", wait_until="networkidle")
    cap.check("logout works after the reload", "/login" in wait_url(page, r"/login", 15), page.url)
    # restore the file
    APPFILE.write_text(src)
new_log = LOG.read_text(errors="replace")[log_before:]
tb = [l for l in new_log.splitlines() if re.search(r"Traceback|Error:|Exception", l)]
cap.check("no traceback in the server log during the run", not tb, "; ".join(tb[:4])[:400])
cap.dump(OUT, {"user": user})
