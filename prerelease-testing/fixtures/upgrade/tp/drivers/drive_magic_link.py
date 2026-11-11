"""Drive reflex-magic-link-auth's upstream demo end to end (dev mode prints the link to the server log).

Usage: drive_magic_link.py <base_url> <out_dir> <label> <server_log>
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

from tpdrive import Capture, browser, wait_text, wait_url

BASE = sys.argv[1].rstrip("/")
OUT = Path(sys.argv[2])
LABEL = sys.argv[3]
LOG = Path(sys.argv[4])
OUT.mkdir(parents=True, exist_ok=True)
SUF = str(int(time.time()))[-6:]
EMAIL = f"user{SUF}@example.com"
cap = Capture()


def shot(page, name):
    page.screenshot(path=str(OUT / f"{LABEL}-{name}.png"), full_page=True)


def find_link(email: str, timeout=20.0) -> str | None:
    deadline = time.time() + timeout
    pat = re.compile(r"(http://\S*/magic-link-auth\?\S+)")
    want = email.replace("@", "%40")
    while time.time() < deadline:
        links = [m for line in LOG.read_text(errors="replace").splitlines() for m in pat.findall(line.strip()) if want in m]
        if links:
            return links[-1]
        time.sleep(0.5)
    return None


def submit_email(page, email):
    page.fill("input[name=email]", email)
    page.get_by_role("button", name="Send Magic Link").click()


with browser() as b:
    ctx = b.new_context()
    page = cap.attach(ctx.new_page(), "tab1")
    navs = []
    page.on("framenavigated", lambda f: f == page.main_frame and navs.append(f.url))
    cap.label = "index"
    page.goto(BASE + "/", wait_until="networkidle")
    cap.check("login form renders", "Enter your email" in wait_text(page, "body", "Enter your email"))

    cap.label = "invalid-email"
    # type=email inputs block "notanemail" via HTML5 validation (no event is sent); an empty
    # email passes the browser and reaches the package's own validation.
    submit_email(page, "")
    cap.check("empty email rejected by package", "Invalid email" in wait_text(page, "body", "Invalid email"))

    cap.label = "send-link"
    submit_email(page, EMAIL)
    page.wait_for_timeout(4000)
    cap.check("redirect to /check-your-email happened", any("/check-your-email" in u for u in navs), str(navs))
    cap.check("stays on /check-your-email (no immediate bounce to /)", "/check-your-email" in page.url, f"final url={page.url} navs={navs}")
    shot(page, "01-check-email")
    link = find_link(EMAIL)
    cap.check("magic link printed by dev server", bool(link), str(link))

    if link:
        cap.label = "open-link"
        p2 = cap.attach(ctx.new_page(), "tab2")
        p2.goto(link, wait_until="networkidle")
        t = wait_text(p2, "body", "Welcome back|Login failed")
        cap.check("magic link logs in and redirects to / (tab2)", "Welcome back" in t and EMAIL in t, t[:200])
        shot(p2, "02-tab2-logged-in")
        cap.label = "tab1-sync"
        t1 = wait_text(page, "body", "Welcome back", timeout=20)
        cap.check("tab1 (check-your-email) follows via LocalStorage sync + moment interval", "Welcome back" in t1, f"url={page.url} text={t1[:120]}")
        shot(page, "03-tab1-synced")

        cap.label = "reuse-link"
        p3 = cap.attach(ctx.new_page(), "tab3")
        ctx_b = b.new_context()
        p3b = cap.attach(ctx_b.new_page(), "ctxB")
        p3b.goto(link, wait_until="networkidle")
        t3 = wait_text(p3b, "body", "Login failed|Welcome back|Login successful")
        cap.check("OTP cannot be reused (fresh context)", "Login failed" in t3, t3[:200])
        ctx_b.close()
        p3.close()

        cap.label = "logout"
        page.bring_to_front()
        page.get_by_role("button", name="Logout").click()
        cap.check("logout shows login form (tab1)", "Enter your email" in wait_text(page, "body", "Enter your email"))
        t2 = wait_text(p2, "body", "Enter your email", timeout=15)
        cap.check("tab2 logged out via LocalStorage sync", "Enter your email" in t2, t2[:120])
        p2.close()

    cap.label = "rate-limit"
    page.goto(BASE + "/", wait_until="networkidle")
    wait_text(page, "body", "Enter your email")
    limited_at = None
    for i in range(1, 9):
        page.goto(BASE + "/", wait_until="networkidle")
        wait_text(page, "body", "Enter your email")
        submit_email(page, f"rl{i}-{EMAIL}")
        page.wait_for_timeout(1200)
        if "too many attempts" in page.locator("body").inner_text().lower() and "/check-your-email" not in page.url:
            limited_at = i
            break
    cap.check("per-IP rate limit eventually triggers", limited_at is not None, f"limited at attempt {limited_at}")
    shot(page, "04-rate-limited")
    ctx.close()

cap.dump(OUT / f"{LABEL}-report.json", {"email": EMAIL})
