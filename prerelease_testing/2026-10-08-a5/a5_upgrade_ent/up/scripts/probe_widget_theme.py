"""Probe how the github-stats widget applies rx.theme(appearance=...) (DOM classes)."""
import sys, time
from playwright.sync_api import sync_playwright
assert "/scratchpad/envs/driver/" in sys.executable
url = sys.argv[1]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    pg.goto(url, wait_until="load")
    pg.get_by_role("heading").first.wait_for(timeout=30000)
    time.sleep(3)
    print(pg.evaluate("""() => Array.from(document.querySelectorAll('.radix-themes, [data-is-root-theme], [class*=dark], [class*=light]'))
        .map(e => e.tagName + ' class=' + e.className + ' data-is-root-theme=' + e.getAttribute('data-is-root-theme') + ' data-appearance=' + e.getAttribute('data-appearance'))"""))
    print("html class:", pg.evaluate("() => document.documentElement.className"), "style:", pg.evaluate("() => document.documentElement.getAttribute('style')"))
    print("heading color:", pg.evaluate("() => getComputedStyle(document.querySelector('h1,h2,h3')).color"))
    b.close()
