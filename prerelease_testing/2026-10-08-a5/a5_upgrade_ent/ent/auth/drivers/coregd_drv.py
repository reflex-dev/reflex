"""Boot a page with localStorage theme='bogus-boot', then navigate client-side; the server log
tells which steps passed the value through Prefs.get_delta. Usage: coregd_drv.py <base>"""
import sys

import playwright  # VENV_GUARD

assert "/scratchpad/envs/driver/" in playwright.__file__, playwright.__file__
from playwright.sync_api import sync_playwright

base = sys.argv[1].rstrip("/")
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    sent = []
    pg.on("websocket", lambda ws: ws.on("framesent", lambda f: sent.append(f[:140]) if isinstance(f, str) and ("hydrate" in f or "update_vars" in f) else None))
    pg.goto(base + "/")
    pg.wait_for_timeout(3000)
    # the compiled client-storage key of Prefs.theme (NOT the color-mode key "theme")
    key = "reflex___state____state.coregd___coregd____prefs.theme_rx_state_"
    print("key", key)
    pg.evaluate("([k]) => localStorage.setItem(k, 'bogus-boot')", [key])
    print("MARK reload", flush=True)
    pg.reload()
    pg.wait_for_timeout(3000)
    print("ls after reload:", pg.evaluate("([k]) => localStorage.getItem(k)", [key]))
    print("theme after reload:", pg.inner_text("#theme"))
    pg.evaluate("([k]) => localStorage.setItem(k, 'bogus-nav')", [key])
    pg.click("#other")
    pg.wait_for_timeout(3000)
    print("theme on /other:", pg.inner_text("#theme2"))
    for s in sent:
        print("SENT", s)
    b.close()
