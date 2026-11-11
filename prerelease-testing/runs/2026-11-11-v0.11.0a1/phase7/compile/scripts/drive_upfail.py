"""Drive upfail: each failing upload from the browser, then a normal one; record UI, toasts, console, /_upload responses.
Usage: drive_upfail.py http://localhost:3300 shot_prefix"""
import json, sys, time
from playwright.sync_api import sync_playwright
base, shot = sys.argv[1].rstrip("/"), sys.argv[2]
out = {"console": [], "upload_responses": []}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    pg.on("console", lambda m: out["console"].append(f"{m.type}: {m.text[:250]}") if m.type in ("error", "warning") or "rror" in m.text else None)
    pg.on("pageerror", lambda e: out["console"].append("pageerror: " + str(e)[:250]))
    pg.on("requestfailed", lambda q: out["console"].append(f"reqfailed {q.url} {q.failure}"))
    def on_resp(r):
        if "/_upload" in r.url:
            try:
                body = r.text()[:300]
            except Exception as e:  # noqa: BLE001
                body = f"<{type(e).__name__}: {str(e)[:100]}>"
            out["upload_responses"].append({"status": r.status, "body": body})
    pg.on("response", on_resp)
    pg.goto(base + "/"); pg.wait_for_selector("#h", timeout=60000); time.sleep(2)
    for btn in ("b-now", "b-later", "b-ok"):
        pg.locator("#u input[type=file]").set_input_files([{"name": f"{btn}.txt", "mimeType": "text/plain", "buffer": b"x" * 2000}])
        time.sleep(0.3)
        pg.click("#" + btn); time.sleep(2.5)
        out[btn] = {
            "n": pg.inner_text("#n"), "prog": pg.inner_text("#prog"),
            "toasts": [t.inner_text()[:200] for t in pg.locator("[data-sonner-toast]").all()],
            "dialogs": [t.inner_text()[:200] for t in pg.locator("[role=alertdialog],[role=dialog]").all()],
        }
        pg.screenshot(path=f"{shot}_{btn}.png")
        pg.click("#b-ping"); time.sleep(1)
        out[btn]["after_ping_done"] = pg.inner_text("#done")
    b.close()
print(json.dumps(out, indent=1))
