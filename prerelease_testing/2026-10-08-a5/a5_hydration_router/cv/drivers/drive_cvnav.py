"""reverify_hydration: client-side-navigation path for computed-var storage rewrites (no full reload).

Load /<v>, wait hydrated, set the storage key to 'bad' from JS (no reload), then navigate client-side
home -> /<v>. The frontend sends update_vars_internal(vars) + on_load_internal on each navigation, so the
computed var's rewrite goes through the per-event delta path (not hydrate_and_load).
Usage: drive_cvnav.py <base> <label> [variant ...]   (variants: a b e_cookie e_session f g)
"""
import json
import sys
import time

from playwright.sync_api import sync_playwright

assert "/scratchpad/envs/driver/" in sys.executable, sys.executable
BASE = sys.argv[1].rstrip("/")
LABEL = sys.argv[2]
VARIANTS = sys.argv[3:] or ["a", "b", "e_cookie", "e_session", "f", "g"]
SLOT = {"a": ("local", "v_a"), "b": ("local", "v_b"), "e_cookie": ("cookie", "v_e_ck"),
        "e_session": ("session", "v_e_ss"), "f": ("local", "v_f"), "g": ("local", "v_g")}

GET = """([kind, key]) => {
  if (kind === 'local') return localStorage.getItem(key);
  if (kind === 'session') return sessionStorage.getItem(key);
  const m = document.cookie.split('; ').find(c => c.startsWith(key + '='));
  return m ? decodeURIComponent(m.slice(key.length + 1)) : null; }"""
SET = """([kind, key]) => {
  if (kind === 'local') localStorage.setItem(key, 'bad');
  else if (kind === 'session') sessionStorage.setItem(key, 'bad');
  else document.cookie = key + '=bad; path=/'; }"""


def hyd(page, settle=1200):
    for _ in range(200):
        try:
            if page.locator("#hyd").first.inner_text(timeout=300) == "hydrated":
                page.wait_for_timeout(settle)
                return True
        except Exception:
            pass
        page.wait_for_timeout(100)
    return False


def ui(page):
    out = {}
    for i in ["var", "check", "plain", "seen"]:
        loc = page.locator(f"#{i}")
        out[i] = loc.first.inner_text() if loc.count() else None
    return out


with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for v in VARIANTS:
        ctx = b.new_context()
        page = ctx.new_page()
        sent = []
        page.on("websocket", lambda ws: ws.on("framesent", lambda d: sent.append(str(d)[:300])))
        page.goto(f"{BASE}/{v}")
        hyd(page)
        page.evaluate(SET, list(SLOT[v]))
        page.click("#nav_home"); page.wait_for_url(f"{BASE}/"); hyd(page)
        st_home = page.evaluate(GET, list(SLOT[v]))
        page.click(f"#nav_{v}"); page.wait_for_url(f"{BASE}/{v}"); hyd(page, 1500)
        st_back = page.evaluate(GET, list(SLOT[v]))
        u1 = ui(page)
        page.click("#probe"); page.wait_for_timeout(1200)
        u2 = ui(page)
        uvi = [s for s in sent if "update_vars_internal" in s]
        res = {"variant": v, "storage_after_nav_home": st_home, "storage_after_nav_back": st_back,
               "ui_after_nav_back": u1, "ui_after_probe": u2, "n_update_vars_internal_sent": len(uvi)}
        ok = st_back in ("", None) and "''" in (u2.get("seen") or "") if v != "g" else u2.get("plain") == "plain=set-by-cv"
        print(f"{LABEL} {v}: {'PASS' if ok else 'FAIL'} {json.dumps(res)}", flush=True)
        ctx.close()
    b.close()
