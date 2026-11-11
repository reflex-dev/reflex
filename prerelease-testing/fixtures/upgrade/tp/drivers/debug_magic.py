import sys, time
from tpdrive import Capture, browser, wait_text
BASE = sys.argv[1]
cap = Capture(ws_frames=True)
with browser() as b:
    ctx = b.new_context()
    page = cap.attach(ctx.new_page())
    page.goto(BASE + "/", wait_until="networkidle")
    print(wait_text(page, "body", "Enter your email"))
    page.wait_for_timeout(1000)
    page.fill("input[name=email]", sys.argv[2])
    print("value:", page.input_value("input[name=email]"))
    page.get_by_role("button", name="Send Magic Link").click()
    page.wait_for_timeout(3000)
    print("BODY:", page.locator("body").inner_text()[:500])
    print("URL:", page.url)
    for w in cap.ws[-12:]:
        print(w["dir"], w["data"][:400])
    for c in cap.console:
        print("CONSOLE", c["type"], c["text"][:300])
    print(cap.page_errors)
