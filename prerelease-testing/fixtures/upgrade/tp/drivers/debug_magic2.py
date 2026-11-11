import sys, time
from tpdrive import Capture, browser, wait_text
BASE = sys.argv[1]
cap = Capture(ws_frames=True)
with browser() as b:
    ctx = b.new_context()
    page = cap.attach(ctx.new_page())
    page.on("framenavigated", lambda f: print("NAV", f.url, flush=True))
    page.on("websocket", lambda ws: print("WS-OPEN", ws.url[:80], flush=True))
    page.goto(BASE + "/", wait_until="networkidle")
    print(wait_text(page, "body", "Enter your email"))
    page.wait_for_timeout(int(sys.argv[3]) if len(sys.argv) > 3 else 1000)
    cap.label = "submit"
    page.fill("input[name=email]", sys.argv[2])
    page.get_by_role("button", name="Send Magic Link").click()
    page.wait_for_timeout(4000)
    print("BODY:", page.locator("body").inner_text()[:300].replace("\n", " | "))
    print("URL:", page.url)
    for w in cap.ws:
        if w["where"] == "submit":
            print(w["dir"], w["data"][:250])
