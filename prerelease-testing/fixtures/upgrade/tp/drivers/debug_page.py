"""Load one URL, wait, and print body text, console messages, page errors, failed requests."""
import sys
from tpdrive import Capture, browser
URL = sys.argv[1]
WAIT = int(sys.argv[2]) if len(sys.argv) > 2 else 3000
SHOT = sys.argv[3] if len(sys.argv) > 3 else None
cap = Capture()
with browser(args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"]) as b:
    ctx = b.new_context(permissions=["microphone", "camera"])
    page = cap.attach(ctx.new_page())
    page.goto(URL, wait_until="networkidle")
    page.wait_for_timeout(WAIT)
    print("URL:", page.url)
    print("BODY:", page.locator("body").inner_text()[:1500])
    if SHOT:
        page.screenshot(path=SHOT, full_page=True)
    for c in cap.console:
        if not c["benign"]:
            print("CONSOLE", c["type"], c["text"][:1500])
    for e in cap.page_errors:
        print("PAGEERROR", e["error"][:2500])
    for r in cap.failed_requests:
        print("FAILEDREQ", r["url"][:200], r["failure"])
    for r in cap.bad_responses:
        print("BADRESP", r["status"], r["url"][:200])
