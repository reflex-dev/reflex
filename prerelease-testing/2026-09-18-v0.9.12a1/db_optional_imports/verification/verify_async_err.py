"""Check whether a failing rx.asession() handler surfaces ANYTHING to the client.

Captures console, page errors, bad responses, JS dialogs (window.alert), DOM toasts
and the raw websocket frames, for a foreground handler and a background task.
"""
import json, sys
from playwright.sync_api import sync_playwright

URL = sys.argv[1]
SHOTS = sys.argv[2]
TAG = sys.argv[3]

console_msgs, page_errors, bad, dialogs, ws = [], [], [], [], []

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    page = ctx.new_page()
    page.on("console", lambda m: console_msgs.append({"t": m.type, "x": m.text[:300]}))
    page.on("pageerror", lambda e: page_errors.append(str(e)[:400]))
    page.on("response", lambda r: bad.append({"u": r.url[:120], "s": r.status}) if r.status >= 400 else None)
    def on_dialog(d):
        dialogs.append({"type": d.type, "message": d.message[:600]})
        d.dismiss()
    page.on("dialog", on_dialog)
    page.on("websocket", lambda w: w.on("framereceived", lambda pl: ws.append(str(pl)[:2500])))

    page.goto(URL, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(1500)
    page.click("#btn-seed"); page.wait_for_timeout(1500)

    def probe(label):
        return {
            "label": label,
            "dialogs": list(dialogs),
            "toast_els": page.eval_on_selector_all(
                "[data-sonner-toast],[data-sonner-toaster],.Toastify__toast,[role=status],[role=alert]",
                "els => els.map(e => e.textContent.slice(0,200))"),
            "body_has_error_text": "An error occurred" in page.inner_text("body"),
            "bg_out": page.inner_text("#bg-out"),
            "authors": page.inner_text("#authors")[:120],
            "console_err": [m for m in console_msgs if m["t"] in ("error", "warning")],
            "page_errors": list(page_errors),
            "bad": list(bad),
        }

    print("== BEFORE ==", json.dumps(probe("before"), indent=1))
    page.click("#btn-async"); page.wait_for_timeout(3000)
    page.screenshot(path=f"{SHOTS}/{TAG}_async_click.png", full_page=True)
    print("== AFTER #btn-async ==", json.dumps(probe("async"), indent=1))
    page.click("#btn-bg"); page.wait_for_timeout(4000)
    page.screenshot(path=f"{SHOTS}/{TAG}_bg_click.png", full_page=True)
    print("== AFTER #btn-bg ==", json.dumps(probe("bg"), indent=1))

    print("== WS frames mentioning toast/alert/error ==")
    for f in ws:
        low = f.lower()
        if "toast" in low or "alert" in low or "error" in low:
            print(f[:1200])
    print("TOTAL_WS:", len(ws), "TOTAL_CONSOLE:", len(console_msgs))
    b.close()
