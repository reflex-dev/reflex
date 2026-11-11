"""Drive the xcut app: REST/WS parity + redaction, awaited protected handler (anon + alice), concurrency, stacked decorator.

Usage: xcut_drv.py <frontend_url> <backend_url> <label> <runlog.jsonl> [--no-auth] [--skip-login]
Writes $SB/apps/enterprise/out/<label>.json and screenshots under $SB/apps/enterprise/shots/<label>_*.png.
Prints [PASS]/[FAIL]/[INFO] lines.
"""

import asyncio
import json
import re
import sys
import time
from pathlib import Path

import httpx
import playwright
from playwright.sync_api import sync_playwright

assert "/envs/driver/" in playwright.__file__, playwright.__file__

FE, BE, LABEL, RUNLOG = sys.argv[1:5]
NO_AUTH = "--no-auth" in sys.argv
SKIP_LOGIN = "--skip-login" in sys.argv
E = Path("/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/apps/enterprise")
(E / "out").mkdir(exist_ok=True)
(E / "shots").mkdir(exist_ok=True)
PUB = "xcut___xcut____pub"
VAULT = "xcut___xcut____vault"
res: dict = {"checks": [], "console": [], "page_errors": [], "http_errors": [], "failed": []}


def check(name, ok, detail=""):
    res["checks"].append({"name": name, "ok": bool(ok), "detail": detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {str(detail)[:300]}", flush=True)


def info(name, detail):
    res.setdefault("info", {})[name] = detail
    print(f"[INFO] {name}: {str(detail)[:400]}", flush=True)


def runlog():
    try:
        return [json.loads(l) for l in Path(RUNLOG).read_text().splitlines() if l.strip()]
    except FileNotFoundError:
        return []


def ran_count():
    return sum(1 for r in runlog() if r["ev"] == "secret_action_RAN")


def text(page, sel, timeout=15000):
    page.wait_for_selector(sel, state="attached", timeout=timeout)
    return page.locator(sel).inner_text()


def wait_text(page, sel, pred, timeout=15):
    end = time.time() + timeout
    t = None
    while time.time() < end:
        try:
            t = page.locator(sel).inner_text(timeout=1000)
            if pred(t):
                return t
        except Exception:
            pass
        time.sleep(0.2)
    return t


cli = httpx.Client(base_url=BE, timeout=30, trust_env=False)


def rest_token():
    r = cli.post("/_reflex/auth/token")
    return r.status_code, (r.json().get("access_token") if r.status_code == 200 else r.text[:200])


def rest(tok, state, handler, body=None, headers=None):
    h = {"Authorization": f"Bearer {tok}", **(headers or {})}
    return cli.post(f"/_reflex/event/{state}/{handler}", headers=h, json=body or {})


def find_key(o, key):
    if isinstance(o, dict):
        if key in o:
            return o[key]
        for v in o.values():
            r = find_key(v, key)
            if r is not None:
                return r
    if isinstance(o, list):
        for v in o:
            r = find_key(v, key)
            if r is not None:
                return r
    return None


with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    page = ctx.new_page()
    page.on("console", lambda m: res["console"].append({"type": m.type, "text": m.text[:400]}) if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: res["page_errors"].append(str(e)[:500]))
    page.on("response", lambda r: res["http_errors"].append({"url": r.url, "status": r.status}) if r.status >= 400 else None)
    page.on("requestfailed", lambda r: res["failed"].append({"url": r.url, "failure": r.failure}))
    page.goto(FE + "/")
    who = wait_text(page, "#anon, #signed-in", lambda t: bool(t), 60)
    check("index renders (anonymous)", who and "anonymous" in who, who)
    page.wait_for_timeout(1000)

    # REST/WS parity
    page.click("#probe")
    ws_info = wait_text(page, "#info", lambda t: '"via":"ws"' in t.replace(" ", ""), 15)
    try:
        ws_info = json.loads(ws_info)
    except Exception:
        pass
    info("ws probe", ws_info)
    st, tok = rest_token()
    check("REST anonymous token issued", st == 200, st)
    r = rest(tok, PUB, "probe", {"via": "rest"}, {"User-Agent": "xcut-rest", "X-Forwarded-For": "203.0.113.9"})
    check("REST probe 200", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
    rest_body = r.text
    rs = cli.post("/_reflex/retrieve_state", headers={"Authorization": f"Bearer {tok}"})
    rest_state = rs.json() if rs.status_code == 200 else {}
    rest_info = find_key(rest_state, "info") or find_key(r.json() if r.status_code == 200 else {}, "info")
    info("rest probe", rest_info)
    if isinstance(ws_info, dict) and isinstance(rest_info, dict):
        same_keys = {k: (ws_info.get(k), rest_info.get(k)) for k in ("client_ip", "client_token_len", "session_id_set", "xff")}
        info("parity ws vs rest (client_ip, token len, session_id set, xff)", same_keys)
        check("client_ip same over ws and REST (spoofed XFF ignored)", ws_info.get("client_ip") == rest_info.get("client_ip"), same_keys["client_ip"])
    # redaction: the browser's client token / cookies must not appear in REST bodies
    btoken = page.evaluate("() => sessionStorage.getItem('token')")
    cookies = page.evaluate("() => document.cookie")
    rest_blob = rest_body + rs.text
    nonempty = re.findall(r'"(client_token|session_id)"\s*:\s*"([^"]+)"', rest_blob)
    check("REST responses: client_token/session_id redacted (empty)", not nonempty, [(k, v[:6]) for k, v in nonempty][:4])
    check("REST responses do not contain the REST bearer token", tok not in rest_blob, "")
    check("browser token not in REST bodies", not btoken or btoken not in rest_blob, btoken and btoken[:6])
    html = page.content()
    check("page DOM has no client token", not btoken or btoken not in html, "")

    # awaited protected handler from anon
    before = ran_count()
    page.click("#call-protected")
    page.wait_for_timeout(2500)
    info("anon: url after awaited protected call (ws)", page.url)
    if not page.url.rstrip("/").endswith(FE.split("//")[1]):
        page.goto(FE + "/")
        wait_text(page, "#anon, #signed-in", lambda t: bool(t), 30)
    aw = wait_text(page, "#awaited", lambda t: t.startswith("result="), 15)
    check("anon: await Vault.secret_action() returns None", aw == "result=None", aw)
    check("anon: protected handler did not run (ws, awaited)", ran_count() == before, f"RAN {ran_count() - before}x")
    page.click("#bg-call-protected")
    page.wait_for_timeout(2500)
    info("anon: url after bg awaited protected call", page.url)
    if not page.url.rstrip("/").endswith(FE.split("//")[1]):
        page.goto(FE + "/")
        wait_text(page, "#anon, #signed-in", lambda t: bool(t), 30)
    awb = wait_text(page, "#awaited-bg", lambda t: t.startswith("result="), 15)
    check("anon: background-task await returns None", awb == "result=None", awb)
    check("anon: protected handler did not run (bg awaited)", ran_count() == before, f"RAN {ran_count() - before}x")
    r = rest(tok, PUB, "call_protected")
    info("REST anon call_protected", f"{r.status_code} {r.text[:300]}")
    r2 = rest(tok, VAULT, "secret_action")
    info("REST anon direct Vault.secret_action", f"{r2.status_code} {r2.text[:300]}")
    page.wait_for_timeout(500)
    check("anon REST: protected handler did not run (awaited or direct)", ran_count() == before, f"RAN {ran_count() - before}x")
    page.screenshot(path=str(E / "shots" / f"{LABEL}_anon.png"))

    # concurrency over the websocket
    page.click("#reset")
    page.wait_for_timeout(500)
    for _ in range(5):
        page.click("#inc", delay=0)
    page.click("#bg-start")
    n = wait_text(page, "#n", lambda t: t == "5", 20)
    bg = wait_text(page, "#bg", lambda t: t == "10", 20)
    check("ws: 5 rapid slow_inc -> n == 5 (serialized per token)", n == "5", n)
    check("ws: background task -> bg == 10", bg == "10", bg)
    page.click("#stacked-btn")
    s = wait_text(page, "#stacked", lambda t: t == "1", 10)
    check("rxe.event stacked over rx.event works", s == "1", s)

    # concurrency over REST, same token
    async def burst():
        async with httpx.AsyncClient(base_url=BE, timeout=60, trust_env=False) as ac:
            h = {"Authorization": f"Bearer {tok}"}
            t0 = time.time()
            rs_ = await asyncio.gather(*[ac.post(f"/_reflex/event/{PUB}/slow_inc", headers=h, json={"tag": f"r{i}"}) for i in range(5)])
            return [x.status_code for x in rs_], time.time() - t0
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(1) as ex:
        codes, dt = ex.submit(lambda: asyncio.run(burst())).result()
    rs = cli.post("/_reflex/retrieve_state", headers={"Authorization": f"Bearer {tok}"})
    rn = find_key(rs.json(), "n") if rs.status_code == 200 else None
    check("REST: 5 concurrent slow_inc on one token -> n == 5", rn == 5, f"codes={codes} n={rn} dt={dt:.2f}s")

    if not NO_AUTH and not SKIP_LOGIN:
        page.goto(FE + "/vault")
        try:
            page.wait_for_url(re.compile("/login"), timeout=20000)
            page.get_by_role("button", name=re.compile("Login with")).first.click()
            page.wait_for_url(re.compile("/oauth2/authorize"), timeout=20000)
            page.locator('button[name="sub"][value="alice"]').click()
            page.wait_for_url(re.compile("/vault"), timeout=30000)
            v = wait_text(page, "#vault", lambda t: t == "vault-content", 30)
            check("login as alice via mock IdP lands on /vault", v == "vault-content", page.url)
            before = ran_count()
            page.click("#call-protected")
            aw = wait_text(page, "#awaited", lambda t: t.startswith("result="), 15)
            check("alice: await Vault.secret_action() returns value", aw == "result='secret-value-for-alice'", aw)
            check("alice: protected handler ran once", ran_count() == before + 1, f"RAN {ran_count() - before}x")
            page.click("#direct")
            ran = wait_text(page, "#ran", lambda t: t == "2", 10)
            check("alice: direct protected click updates Vault.ran", ran == "2", ran)
            ck = ctx.cookies()
            info("cookies after login", [(c["name"], c["httpOnly"], c["sameSite"]) for c in ck])
            page.screenshot(path=str(E / "shots" / f"{LABEL}_alice.png"))
            page.click("#logout")
            page.wait_for_timeout(3000)
            if "end_session" in page.url:
                page.get_by_role("button", name="End session", exact=True).click()
                page.wait_for_timeout(3000)
            info("url after logout", page.url)
            page.goto(FE + "/")
            wait_text(page, "#anon, #signed-in", lambda t: bool(t), 30)
            before = ran_count()
            page.click("#call-protected")
            page.wait_for_timeout(2500)
            info("after logout: url after awaited protected call", page.url)
            if "/login" in page.url:
                page.goto(FE + "/")
                wait_text(page, "#anon, #signed-in", lambda t: bool(t), 30)
            aw = wait_text(page, "#awaited", lambda t: t == "result=None", 15)
            page.wait_for_timeout(500)
            check("after logout: awaited protected returns None and does not run", aw == "result=None" and ran_count() == before, f"{aw} RAN {ran_count() - before}x")
        except Exception as e:
            check("login flow", False, repr(e)[:300])
            page.screenshot(path=str(E / "shots" / f"{LABEL}_login_fail.png"))
    b.close()

res["console_nonbenign"] = [c for c in res["console"] if "favicon" not in c["text"] and "Hey developer" not in c["text"]]
print("console errors/warnings:", json.dumps(res["console_nonbenign"])[:1500])
print("page errors:", res["page_errors"][:5])
print("http>=400:", [h for h in res["http_errors"] if "favicon" not in h["url"]][:10])
print("failed requests:", res["failed"][:10])
(E / "out" / f"{LABEL}.json").write_text(json.dumps(res, indent=1, default=str))
print(f"SUMMARY {LABEL}: {sum(c['ok'] for c in res['checks'])}/{len(res['checks'])} pass")
