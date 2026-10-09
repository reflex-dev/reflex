"""magic-link demo in REAL prod mode (no ML_FORCE_DEV): the form must render with the captcha widget and a
submit must be rejected by the package/demo ("Captcha verification failed") because Google is unreachable.

Usage: drive_magic_prod_real.py <base_url> <out_json>
"""
import sys

from tpdrive import Capture, browser, wait_text

BASE = sys.argv[1].rstrip("/")
cap = Capture()
with browser() as b:
    ctx = b.new_context()
    page = cap.attach(ctx.new_page(), "main")
    page.goto(BASE + "/", wait_until="networkidle")
    cap.check("form renders in prod", "Enter your email" in wait_text(page, "body", "Enter your email"))
    page.wait_for_timeout(2000)
    page.fill("input[name=email]", "real-prod@example.com")
    page.get_by_role("button", name="Send Magic Link").click()
    t = wait_text(page, "body", "Captcha verification failed|Invalid email|Too many", timeout=10)
    cap.check("submit without a solved captcha is rejected", "Captcha verification failed" in t, t[:200])
    cap.check("stays on the login page", page.url.rstrip("/") == BASE, page.url)
    page.screenshot(path=sys.argv[2].replace(".json", ".png"), full_page=True)
cap.dump(sys.argv[2])
