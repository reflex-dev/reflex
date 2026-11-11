"""reflex-local-auth (SQLModel, sync rx.session) + Base blog in the same app."""
import sys

from pwlib import SHOTS, Cap, browser, check

base, tag = sys.argv[1], sys.argv[2]
cap = Cap()
with browser() as b:
    page = b.new_page()
    cap.attach(page)
    page.goto(base + "/register")
    page.wait_for_selector("#username", timeout=30000)
    page.wait_for_timeout(1500)
    page.fill("#username", "zed")
    page.fill("#password", "pw123456")
    page.fill("#confirm_password", "pw123456")
    page.click("text=Sign up")
    page.wait_for_timeout(3000)
    print("after register:", page.url, page.inner_text("body")[:200].replace("\n", " | "))
    page.goto(base + "/login")
    page.wait_for_selector("#username")
    page.wait_for_timeout(1000)
    page.fill("#username", "zed")
    page.fill("#password", "pw123456")
    page.click("text=Sign in")
    page.wait_for_timeout(3000)
    print("after login:", page.url)
    page.goto(base + "/")
    page.wait_for_selector(".post-row", timeout=20000)
    check("blog (Base, async) renders alongside local-auth", len(page.query_selector_all(".post-row")) >= 3)
    page.screenshot(path=f"{SHOTS}/{tag}.png", full_page=True)
cap.report()
