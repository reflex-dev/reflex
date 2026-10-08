"""a5_hydration_router Part 1 driver for src/rtr (reflex#7360).

Usage: rtr_drive.py FRONT BACKEND OUT_JSON [--reload-file APP_PY] [--no-secrets] [--steps a,b]

Sets a plain cookie + an HttpOnly cookie (from the app's /setck server route) + credential headers (context
extra_http_headers, applied by Chromium to every request incl. the websocket upgrade), then walks the router matrix:
first load, reload, client nav (rx.link) to every on_load flavour, query change, redirect chains, back/forward,
direct loads, /front frontend rendering, two tabs, sync=True storage (update_vars_internal), and (dev) a backend hot
reload = websocket reconnect. Captures EVERY websocket frame (both directions), document responses, DOM, storage and
console, and scans them for the secret values.
"""

import json
import sys
import time

import playwright

assert "/envs/driver/" in playwright.__file__, playwright.__file__

from playwright.sync_api import sync_playwright  # noqa: E402

CHROMIUM = "/opt/pw-browsers/chromium"
SECRETS = {
    "ck_plain": "PLAINSECRET7a1",
    "ck_httponly": "HTTPONLYSECRET9f3",
    "authorization": "AUTHSECRET41c",
    "proxy-authorization": "PROXYAUTHSECRET5d",
    "cf-access-jwt-assertion": "CFJWTSECRET88b",
    "x-forwarded-access-token": "XFATSECRET2e0",
    "x-auth-request-access-token": "XARATSECRET6b2",
    "x-amzn-oidc-accesstoken": "AMZNSECRET3c9",
    "x-amzn-oidc-data": "AMZNDATASECRET1f",
    "x-goog-iap-jwt-assertion": "IAPSECRET77e",
}
HEADERS = {
    "Authorization": "Bearer " + SECRETS["authorization"],
    # Proxy-Authorization cannot be set by Chromium extra headers (net::ERR_INVALID_ARGUMENT): covered by ws_raw.py
    "Cf-Access-Jwt-Assertion": SECRETS["cf-access-jwt-assertion"],
    "X-Forwarded-Access-Token": SECRETS["x-forwarded-access-token"],
    "X-Auth-Request-Access-Token": SECRETS["x-auth-request-access-token"],
    "X-Amzn-Oidc-Accesstoken": SECRETS["x-amzn-oidc-accesstoken"],
    "X-Amzn-Oidc-Data": SECRETS["x-amzn-oidc-data"],
    "X-Goog-Iap-Jwt-Assertion": SECRETS["x-goog-iap-jwt-assertion"],
}
FRONT_IDS = ["f_page_path", "f_params", "f_url", "f_url_path", "f_qp", "f_ua", "f_cookie", "f_cookie_idx",
             "f_cookie_contains", "f_raw_cookie_idx", "f_raw_cookie_get", "f_raw_auth_idx", "f_raw", "f_raw_fe",
             "f_headers_all", "f_ip", "f_tok", "f_router_all", "cv_router", "cv_has_cookie", "cv_has_auth"]

args = sys.argv[1:]
FRONT, BACKEND, OUT = args[0].rstrip("/"), args[1].rstrip("/"), args[2]
RELOAD_FILE = args[args.index("--reload-file") + 1] if "--reload-file" in args else None
NO_SECRETS = "--no-secrets" in args
ONLY = set(args[args.index("--steps") + 1].split(",")) if "--steps" in args else None

frames = []  # (t, tab, dir, url, payload)
docs = []  # (url, status, body)
console = []
failed = []
results = {"front": FRONT, "steps": [], "anomalies": []}
T0 = time.time()


def hook(page, tab):
    def on_ws(ws):
        frames.append((round(time.time() - T0, 3), tab, "open", ws.url, ""))
        ws.on("framereceived", lambda p: frames.append((round(time.time() - T0, 3), tab, "in", ws.url, p if isinstance(p, str) else repr(p))))
        ws.on("framesent", lambda p: frames.append((round(time.time() - T0, 3), tab, "out", ws.url, p if isinstance(p, str) else repr(p))))
        ws.on("close", lambda w: frames.append((round(time.time() - T0, 3), tab, "close", ws.url, "")))

    page.on("websocket", on_ws)
    page.on("console", lambda m: console.append((tab, m.type, m.text[:500])))
    page.on("pageerror", lambda e: console.append((tab, "pageerror", str(e)[:500])))
    page.on("requestfailed", lambda r: failed.append((tab, r.url, r.failure)))

    def on_resp(r):
        if r.status >= 400:
            failed.append((tab, r.url, r.status))
        if r.request.resource_type == "document":
            try:
                docs.append((r.url, r.status, r.text()))
            except Exception as e:  # noqa: BLE001
                docs.append((r.url, r.status, f"<body unavailable {e}>"))

    page.on("response", on_resp)


def loglen(page):
    try:
        return int(page.inner_text("#loglen", timeout=2000).split(":")[-1].strip() or 0)
    except Exception:  # noqa: BLE001
        return -1


def settle(page, quiet=1.0, cap=10.0):
    t_end = time.time() + cap
    last = None
    stable_since = time.time()
    while time.time() < t_end:
        try:
            cur = (page.url, loglen(page), page.inner_text("#hydrated", timeout=2000))
        except Exception:  # noqa: BLE001
            cur = ("err",)
        if cur != last:
            last, stable_since = cur, time.time()
        elif time.time() - stable_since >= quiet and cur[-1] == "true":
            return
        time.sleep(0.15)
    results["anomalies"].append(f"settle timeout at {page.url} last={last}")


def read_log(page):
    out = []
    for el in page.query_selector_all(".logline"):
        try:
            out.append(json.loads(el.inner_text()))
        except Exception as e:  # noqa: BLE001
            out.append({"parse_err": str(e)})
    return out


def clear(page):
    page.click("#clear")
    t_end = time.time() + 5
    while time.time() < t_end and loglen(page) != 0:
        time.sleep(0.1)


def step(name, page, action, tab="t1", pre_clear=True, wait_extra=0.0, front=False):
    if ONLY and name.split("_")[0] not in ONLY:
        return
    if pre_clear:
        try:
            clear(page)
        except Exception as e:  # noqa: BLE001
            results["anomalies"].append(f"{name}: clear failed {e}")
    nf = len(frames)
    t = time.time()
    try:
        action()
    except Exception as e:  # noqa: BLE001
        results["anomalies"].append(f"{name}: action failed {e!r}"[:400])
    time.sleep(wait_extra)
    settle(page)
    rec = {"step": name, "tab": tab, "url": page.url, "log": read_log(page), "dt": round(time.time() - t, 2),
           "frames": len(frames) - nf}
    if front:
        fr = {}
        for i in FRONT_IDS:
            try:
                fr[i] = page.inner_text("#" + i, timeout=3000)
            except Exception as e:  # noqa: BLE001
                fr[i] = f"<missing {type(e).__name__}>"
        rec["front"] = fr
    results["steps"].append(rec)
    print(f"{name}: url={page.url} log={[e.get('tag') for e in rec['log']]} dt={rec['dt']}", flush=True)


def nav_click(page, href):
    sel = "#nav" + href.replace("/", "_").replace("?", "_q_").replace("=", "_")
    return lambda: page.click(sel)


with sync_playwright() as p:
    br = p.chromium.launch(executable_path=CHROMIUM)
    ctx = br.new_context(extra_http_headers={} if NO_SECRETS else HEADERS)
    if not NO_SECRETS:
        host = FRONT.split("//")[1].split(":")[0]
        ctx.add_cookies([{"name": "rtr_plain", "value": SECRETS["ck_plain"], "domain": host, "path": "/"}])
    page = ctx.new_page()
    hook(page, "t1")
    if not NO_SECRETS:
        r = page.goto(BACKEND + "/setck")
        results["setck"] = [r.status if r else None, page.inner_text("body")[:40]]
        results["cookies_in_browser"] = [(c["name"], c["httpOnly"]) for c in ctx.cookies()]
    page.goto(FRONT + "/")
    settle(page)
    step("S01_first_load", page, lambda: None, pre_clear=False)
    step("S02_reload", page, lambda: page.reload())
    step("S03_probe", page, lambda: page.click("#probe"))
    for i, href in enumerate(["/multi", "/chain", "/bg", "/post/hello?x=1", "/post/hello?x=2", "/post/other", "/files",
                              "/files/a/b/c", "/redir", "/redir-chain", "/fe"]):
        step(f"S1{i:02d}_nav{href}", page, nav_click(page, href), wait_extra=1.2 if href == "/bg" else 0.3)
    step("S20_back", page, lambda: page.go_back(), wait_extra=0.5)
    step("S21_back", page, lambda: page.go_back(), wait_extra=0.5)
    step("S22_forward", page, lambda: page.go_forward(), wait_extra=0.5)
    for i, path in enumerate(["/post/hello?x=1", "/files/a/b/c?q=z", "/files", "/redir-chain", "/fe", "/bg", "/multi",
                              "/chain"]):
        step(f"S3{i}_goto{path}", page, lambda path=path: page.goto(FRONT + path), wait_extra=1.2 if path == "/bg" else 0.3)
    step("S40_probe_after_bg", page, lambda: page.click("#probe"))
    step("S41_goto/front", page, lambda: page.goto(FRONT + "/front?fq=1"), front=True)
    step("S42_send_headers", page, lambda: page.click("#send_headers"), front=True)
    results["recv_headers"] = page.inner_text("#recv")
    step("S43_send_cookie", page, lambda: page.click("#send_cookie"))
    results["recv_cookie"] = page.inner_text("#recv")
    results["front_html_has"] = {k: (v in page.content()) for k, v in SECRETS.items()}
    step("S44_nav_front_from_index", page, lambda: (page.goto(FRONT + "/"), settle(page), page.click("#nav_front")), front=True)
    # two tabs
    page2 = ctx.new_page()
    hook(page2, "t2")
    page2.goto(FRONT + "/post/tab2?t=2")
    settle(page2)
    step("S50_tab2_first_load", page2, lambda: None, tab="t2", pre_clear=False)
    step("S51_tab1_probe_after_tab2", page, lambda: page.click("#probe"))
    step("S52_tab2_probe", page2, lambda: page2.click("#probe"), tab="t2")
    # sync=True storage -> update_vars_internal in the other tab
    step("S60_tab1_sync", page, lambda: page.goto(FRONT + "/sync"))
    step("S61_tab2_sync", page2, lambda: page2.goto(FRONT + "/sync"), tab="t2")
    nf = len(frames)
    page.click("#s1")
    time.sleep(1.5)
    page2.click("#s2")
    time.sleep(1.5)
    results["sync"] = {"t1": page.inner_text("#synced"), "t2": page2.inner_text("#synced"),
                       "uvi_frames": [f[:4] + (f[4][:300],) for f in frames[nf:] if "update_vars_internal" in f[4]]}
    # backend hot reload (dev) -> websocket reconnect -> hydrate again
    if RELOAD_FILE:
        page.goto(FRONT + "/post/recon?r=1")
        settle(page)
        nf = len(frames)
        with open(RELOAD_FILE, "a") as f:
            f.write(f"\n# reload {time.time()}\n")
        t_end = time.time() + 60
        while time.time() < t_end:
            if any(f[2] == "open" for f in frames[nf:]) and any(f[2] == "in" and "delta" in f[4] for f in frames[nf:]):
                break
            time.sleep(0.3)
        time.sleep(2)
        settle(page)
        results["reconnect"] = {"opens": sum(1 for f in frames[nf:] if f[2] == "open"),
                                "closes": sum(1 for f in frames[nf:] if f[2] == "close"),
                                "frames_after": len(frames) - nf, "log_after": read_log(page)}
        step("S70_probe_after_reconnect", page, lambda: page.click("#probe"))
        step("S71_nav_after_reconnect", page, nav_click(page, "/post/hello?x=1"))
        results["reconnect_frame_secrets"] = {k: sum(v in f[4] for f in frames[nf:]) for k, v in SECRETS.items()}
    results["storage"] = page.evaluate("() => ({ls: {...localStorage}, ss: {...sessionStorage}, ck: document.cookie})")
    br.close()

# leak scan
leaks = {}
for k, v in SECRETS.items():
    hits = [f for f in frames if v in f[4]]
    leaks[k] = {"in": sum(1 for f in hits if f[2] == "in"), "out": sum(1 for f in hits if f[2] == "out"),
                "example": (lambda f: f[:4] + (f[4][max(0, f[4].find(v) - 160):f[4].find(v) + 40],))(hits[0]) if hits else None,
                "docs": sum(1 for d in docs if v in d[2]),
                "console": sum(1 for c in console if v in c[2])}
results["leaks"] = leaks
results["n_frames"] = {"in": sum(1 for f in frames if f[2] == "in"), "out": sum(1 for f in frames if f[2] == "out"),
                       "open": sum(1 for f in frames if f[2] == "open")}
results["n_docs"] = len(docs)
results["console"] = [c for c in console if c[1] in ("error", "warning", "pageerror")]
results["console_all_n"] = len(console)
results["failed"] = failed
with open(OUT, "w") as f:
    json.dump(results, f, indent=1)
with open(OUT.replace(".json", ".frames.jsonl"), "w") as f:
    for fr in frames:
        f.write(json.dumps(fr) + "\n")
print("LEAKS", json.dumps({k: (v["in"], v["out"], v["docs"], v["console"]) for k, v in leaks.items()}))
print("NFRAMES", results["n_frames"], "anomalies", results["anomalies"][:5])
print("CONSOLE", results["console"][:6])
print("FAILED", failed[:6])
