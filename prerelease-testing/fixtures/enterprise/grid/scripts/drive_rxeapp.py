"""Check rxe.App specifics: google_font head links, Built-with-Reflex badge, basic state, nav.

Usage: drive_rxeapp.py <base_url> <out_dir> <expected_venv> <label> <expect_badge:0|1>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from qa_common import Session, assert_driver_and_server  # noqa: E402

base, out, venv, label, expect_badge = sys.argv[1:6]
expect_badge = expect_badge == "1"
info = assert_driver_and_server(venv)

with Session(f"rxeapp-{label}", Path(out)) as s:
    s.note(f"guard: {info['versions']}")
    p = s.new_page(label="rxeapp")
    p.goto(base + "/", wait_until="networkidle")
    p.wait_for_timeout(1500)
    links = p.evaluate("() => [...document.head.querySelectorAll('link')].map(l => ({rel: l.rel, href: l.href, co: l.crossOrigin}))")
    gf = [l for l in links if "fonts.g" in l["href"]]
    s.note(f"google font links: {gf}")
    s.check("google_font: preconnect googleapis + gstatic(crossorigin=anonymous) + css2 stylesheet in <head>",
            any(l["rel"] == "preconnect" and l["href"].startswith("https://fonts.googleapis.com") for l in gf)
            and any(l["rel"] == "preconnect" and "fonts.gstatic.com" in l["href"] and l["co"] == "anonymous" for l in gf)
            and any(l["rel"] == "stylesheet" and l["href"] == "https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap" for l in gf), gf)
    raw = p.evaluate("() => document.documentElement.outerHTML")
    s.check("google_font links are present in the served HTML head (before hydration, prod prerender)", "fonts.googleapis.com/css2?family=Inter" in raw)
    ff = p.locator("#t").evaluate("e => getComputedStyle(e).fontFamily")
    s.check("app style font_family applies (Inter, sans-serif)", "Inter" in ff, ff)
    badge = p.locator("a:has-text('Built with Reflex')")
    s.check(f"badge {'present' if expect_badge else 'absent'}", (badge.count() > 0) == expect_badge, badge.count())
    if badge.count():
        s.note(f"badge href: {badge.first.get_attribute('href')} style.position: {badge.first.evaluate('e => getComputedStyle(e).position')}")
    p.click("#inc")
    p.wait_for_timeout(700)
    s.check("state event works", p.locator("#n").inner_text() == "1", p.locator("#n").inner_text())
    p.click("#to-other")
    p.wait_for_timeout(1000)
    s.check("client-side nav to /other (badge persists across pages)", p.locator("#other").count() == 1 and (p.locator("a:has-text('Built with Reflex')").count() > 0) == expect_badge)
    s.shot(p, "other")
