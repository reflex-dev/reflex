"""Verify prod-built static output in a real browser (no backend).

Checks the SSR/CSS-baked results of the prod compile:
- #6776: deprecated App(theme=...) + explicit RadixThemesPlugin -> crimson accent
  applied (data-accent-color + computed --accent-9 CSS var)
- #6951: "Built with Reflex" badge present with urlencoded ref href
Usage: python drive_prod_static.py <base_url> <outdir>
"""

import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:3381"
OUT = sys.argv[2].rstrip("/") if len(sys.argv) > 2 else "."
EXPECTED_HREF = "https://reflex.dev/?ref=test%20ref%26x%3D1"

console_msgs = []

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = browser.new_context().new_page()
    page.on("console", lambda m: console_msgs.append((m.type, m.text)))
    page.goto(BASE + "/", wait_until="domcontentloaded", timeout=40000)
    page.wait_for_timeout(2500)

    theme = page.evaluate(
        """() => {
            const el = document.querySelector('.radix-themes[data-accent-color=\"crimson\"]')
                     || document.querySelector('.radix-themes');
            if (!el) return {present:false};
            const cs = getComputedStyle(el);
            return {present:true, accent: el.getAttribute('data-accent-color'),
                    radius: el.getAttribute('data-radius'),
                    accent9: cs.getPropertyValue('--accent-9').trim()};
        }"""
    )
    print("THEME:", theme)

    badge = page.evaluate(
        """() => {
            const links = Array.from(document.querySelectorAll('a[href*=\"reflex.dev\"]'));
            return links.map(a => ({href: a.getAttribute('href'), text: (a.textContent||'').trim().slice(0,40)}));
        }"""
    )
    print("BADGE_LINKS:", badge)

    href_ok = any(b["href"] == EXPECTED_HREF for b in badge)
    theme_ok = theme.get("present") and theme.get("accent") == "crimson" and theme.get("accent9")
    page.screenshot(path=OUT + "/prod_static.png", full_page=True)
    browser.close()

print("\nCONSOLE:")
for t, m in console_msgs:
    print(f"  [{t}] {m[:200]}")

print("\nRESULTS:")
print(f"  [{'pass' if theme_ok else 'FAIL'}] prod_theme_crimson_applied: {theme}")
print(f"  [{'pass' if href_ok else 'FAIL'}] prod_badge_referrer_urlencoded: expected {EXPECTED_HREF!r}")
sys.exit(0 if (theme_ok and href_ok) else 1)
