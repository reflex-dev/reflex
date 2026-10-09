"""a3_hydration: reflex-local-auth demo x #7493 boot echo.
Fresh profile writes nothing; register+login stores `_auth_token`; reload/second tab stay logged in; counts how often
`auth_token` rides in inbound deltas on a reload (echo); cross-tab logout + reload; bogus token -> anonymous; frames.
Usage: la_storage.py BASE OUT_JSON
"""
import json
import re
import sys
import time

from playwright.sync_api import sync_playwright

import os  # noqa: E402
assert f"/envs/{os.environ.get('DRV_VENV', 'driver')}/" in sys.executable, sys.executable
BASE, OUT = sys.argv[1].rstrip("/"), sys.argv[2]
SUF = str(int(time.time()))[-6:]
U, PW = f"echo{SUF}", "correct-horse-1"
BENIGN = ("Hey developer", "React DevTools", "[vite]", "favicon")
res = {"checks": []}


def check(name, ok, detail=""):
    res["checks"].append({"name": name, "ok": bool(ok), "detail": str(detail)[:300]})
    print(("PASS " if ok else "FAIL ") + name + (f" :: {str(detail)[:200]}" if not ok else ""), flush=True)


class Rec:
    def __init__(self, page, tag):
        self.page, self.tag, self.frames, self.cons = page, tag, [], []
        page.on("websocket", self._ws)
        page.on("console", lambda m: m.type in ("error", "warning") and not any(b in m.text for b in BENIGN) and self.cons.append(m.text[:200]))

    def _ws(self, ws):
        if "_event" in ws.url:
            ws.on("framereceived", lambda p: self.frames.append(("in", p if isinstance(p, str) else "")))
            ws.on("framesent", lambda p: self.frames.append(("out", p if isinstance(p, str) else "")))

    def since(self, n):
        fr = self.frames[n:]
        ins = [p for d, p in fr if d == "in" and p.startswith("42")]
        return {"in_frames": len(ins), "in_bytes": sum(len(p) for p in ins),
                "auth_token_in_deltas": sum(p.count('"auth_token_rx_state_"') for p in ins),
                "auth_token_values": sorted(set(re.findall(r'"auth_token_rx_state_":"([^"]*)"', "".join(ins))))}


def body(page):
    try:
        return page.inner_text("body", timeout=3000)
    except Exception:
        return ""


def wait_for(page, pat, t=15):
    for _ in range(t * 10):
        b = body(page)
        if re.search(pat, b):
            return b
        page.wait_for_timeout(100)
    return body(page)


def ls(page):
    return page.evaluate("() => Object.fromEntries(Object.keys(localStorage).filter(k => !['theme','last_compiled_theme'].includes(k)).map(k => [k, localStorage.getItem(k)]))")


with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    # fresh profile: nothing written
    for path in ("/", "/login", "/protected", "/need2login"):
        ctx = b.new_context()
        p = ctx.new_page()
        p.goto(BASE + path, wait_until="networkidle")
        p.wait_for_timeout(1500)
        check(f"fresh {path}: no client storage written", ls(p) == {} and ctx.cookies() == [], (ls(p), ctx.cookies()))
        ctx.close()
    ctx = b.new_context()
    p = ctx.new_page()
    r = Rec(p, "A")
    p.goto(BASE + "/register", wait_until="networkidle")
    p.wait_for_selector("input#username")
    for k, v in {"username": U, "password": PW, "confirm_password": PW}.items():
        p.fill(f"input#{k}", v)
    p.get_by_role("button", name="Sign up").click()
    wait_for(p, "Registration successful")
    p.wait_for_url(re.compile(r"/login"), timeout=15000)
    p.wait_for_selector("input#username")
    p.fill("input#username", U)
    p.fill("input#password", PW)
    p.get_by_role("button", name="Sign in").click()
    p.wait_for_timeout(1500)
    tok = ls(p).get("_auth_token")
    check("login stores _auth_token in localStorage", bool(tok), ls(p))
    p.goto(BASE + "/user-info", wait_until="networkidle")
    check("user-info shows user", f"Username: {U}" in wait_for(p, f"Username: {U}"))
    n = len(r.frames)
    p.reload(wait_until="networkidle")
    t = wait_for(p, f"Username: {U}")
    p.wait_for_timeout(1000)
    res["reload_frames"] = r.since(n)
    check("reload: still logged in", f"Username: {U}" in t)
    check("reload: token unchanged", ls(p).get("_auth_token") == tok, ls(p))
    print("   reload frames:", res["reload_frames"], flush=True)
    p2 = ctx.new_page()
    r2 = Rec(p2, "B")
    p2.goto(BASE + "/protected", wait_until="networkidle")
    check("second tab logged in", f"private data for {U}" in wait_for(p2, f"private data for {U}"))
    res["tab2_frames"] = r2.since(0)
    # logout in tab A, reload tab B
    p.goto(BASE + "/need2login", wait_until="networkidle")
    wait_for(p, "Accessing this page")
    p.get_by_role("link", name="Logout").first.click()
    check("after logout index shows Login", re.search(r"\bLogin\b", wait_for(p, r"\bLogin\b")) is not None)
    p.wait_for_timeout(800)
    res["ls_after_logout"] = ls(p)
    p2.reload(wait_until="networkidle")
    p2.wait_for_timeout(1500)
    check("tab B logged out after reload", "/login" in p2.url, p2.url)
    p.goto(BASE + "/protected", wait_until="networkidle")
    p.wait_for_timeout(1500)
    check("tab A /protected -> /login after logout", "/login" in p.url, p.url)
    # log in again, then put a bogus token
    p.fill("input#username", U)
    p.fill("input#password", PW)
    p.get_by_role("button", name="Sign in").click()
    p.wait_for_timeout(1500)
    p.evaluate("() => localStorage.setItem('_auth_token', 'bogus-token-123')")
    n = len(r.frames)
    p.goto(BASE + "/protected", wait_until="networkidle")
    p.wait_for_timeout(2000)
    res["bogus_frames"] = r.since(n)
    check("bogus token -> /protected redirects to /login", "/login" in p.url, p.url)
    res["ls_after_bogus"] = ls(p)
    res["console_A"], res["console_B"] = r.cons, r2.cons
    check("no console errors/warnings", not r.cons and not r2.cons, (r.cons, r2.cons))
    b.close()
res["passed"] = sum(c["ok"] for c in res["checks"])
res["total"] = len(res["checks"])
print(f"{res['passed']}/{res['total']} checks; ls_after_logout={res['ls_after_logout']} ls_after_bogus={res['ls_after_bogus']}")
json.dump(res, open(OUT, "w"), indent=1)
