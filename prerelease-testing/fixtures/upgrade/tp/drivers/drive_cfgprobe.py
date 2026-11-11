"""Click the button of apps/cfgprobe and print what the backend worker sees in get_config()."""
import sys

from tpdrive import browser, wait_text

BASE = sys.argv[1].rstrip("/")
with browser() as b:
    p = b.new_page()
    p.goto(BASE + "/", wait_until="networkidle")
    p.wait_for_selector("#show")
    p.wait_for_timeout(1500)
    p.click("#show")
    print(wait_text(p, "#msg", "py=", timeout=15))
