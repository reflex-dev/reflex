"""drive_forkapp.py <base_url> <out.json> [--clients 6] [--shots dir] [--label x]

Driver venv (Playwright). Opens N isolated contexts on the forkapp index, reads each client's token,
then POSTs /api/poke/<token> (lands on an arbitrary worker) and expects every page to render
"poked: 1" (EVT-04: backend-initiated delta routed to the worker holding the socket). Then clicks
inc / note / bg / fetch on every page and checks the results; collects console errors/warnings,
page errors and failed requests per page.
"""

import json
import os
import re
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

assert ("/envs/" + os.environ.get("DRIVER", "driver") + "/") in sys.executable, sys.executable
base = sys.argv[1].rstrip("/")
out = sys.argv[2]
opts = dict(zip(sys.argv[3::2], sys.argv[4::2]))
N = int(opts.get("--clients", "6"))
shots = opts.get("--shots")
label = opts.get("--label", "run")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
BENIGN = re.compile(r"Hey developer.*HydrateFallback|reactrouter\.com/start|\[vite\] (connecting|connected)|Download the React DevTools|favicon")
checks = []


def check(name, ok, detail=""):
    checks.append({"name": name, "ok": bool(ok), "detail": str(detail)[:300]})
    print(("PASS " if ok else "FAIL ") + name + (f": {detail}" if detail else ""))


def text(page, sel):
    return page.locator(sel).inner_text()


def wait_text(page, sel, pred, timeout=15.0):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        t = text(page, sel)
        if pred(t):
            return t
        time.sleep(0.1)
    return text(page, sel)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pages, logs = [], []
    for i in range(N):
        ctx = browser.new_context()
        page = ctx.new_page()
        entry = {"console": [], "errors": [], "failed": [], "http_err": []}
        page.on("console", lambda m, e=entry: e["console"].append(f"{m.type}: {m.text}") if m.type in ("error", "warning") and not BENIGN.search(m.text) else None)
        page.on("pageerror", lambda ex, e=entry: e["errors"].append(str(ex)))
        page.on("requestfailed", lambda r, e=entry: e["failed"].append(f"{r.url} {r.failure}") if "favicon" not in r.url else None)
        page.on("response", lambda r, e=entry: e["http_err"].append(f"{r.status} {r.url}") if r.status >= 400 and "favicon" not in r.url else None)
        page.goto(base + "/", wait_until="load")
        pages.append(page)
        logs.append(entry)
    tokens, pids = [], []
    for i, page in enumerate(pages):
        t = wait_text(page, "#token", lambda s: len(s) > 20, 30)
        tok = t.split("token:", 1)[1].strip()
        tokens.append(tok)
        pidtxt = wait_text(page, "#pid", lambda s: re.search(r"\d+", s) is not None, 10)
        pids.append(int(re.search(r"\d+", pidtxt).group()))
    check("tokens_present", all(len(t) > 20 for t in tokens), f"{len(tokens)} tokens")
    check("onload_pids", all(pids), f"socket worker pids: {sorted(set(pids))}")
    # EVT-04: poke each client from an arbitrary worker.
    poke_pids = []
    for tok in tokens:
        req = urllib.request.Request(f"{base}/api/poke/{tok}", method="POST")
        with opener.open(req, timeout=10) as r:
            poke_pids.append(json.load(r)["pid"])
    delivered = 0
    cross = 0
    details = []
    for i, page in enumerate(pages):
        t = wait_text(page, "#poked", lambda s: "poked: 1" in s, 15)
        ok = "poked: 1" in t
        delivered += ok
        cross += poke_pids[i] != pids[i]
        details.append(f"client{i}: socket_pid={pids[i]} poke_pid={poke_pids[i]} -> {t!r}")
    check("evt04_poke_delivered", delivered == N, f"{delivered}/{N} delivered, {cross}/{N} cross-worker; " + "; ".join(details))
    # second poke round (counts accumulate)
    for tok in tokens:
        req = urllib.request.Request(f"{base}/api/poke/{tok}", method="POST")
        opener.open(req, timeout=10).read()
    d2 = sum("poked: 2" in wait_text(page, "#poked", lambda s: "poked: 2" in s, 15) for page in pages)
    check("evt04_second_round", d2 == N, f"{d2}/{N}")
    # interactions
    for i, page in enumerate(pages):
        page.click("#inc")
        page.click("#inc")
        t = wait_text(page, "#count", lambda s: "count: 2" in s, 10)
        check(f"inc_client{i}", "count: 2" in t, t)
    for i, page in enumerate(pages):
        page.click("#note")
        t = wait_text(page, "#rows", lambda s: re.search(r"rows: [1-9]", s) is not None, 10)
        check(f"note_client{i}", re.search(r"rows: [1-9]", t) is not None, t)
    for i, page in enumerate(pages):
        page.click("#bgbtn")
    for i, page in enumerate(pages):
        t = wait_text(page, "#bg", lambda s: "bg-done" in s, 15)
        check(f"bg_client{i}", "bg-done" in t, t)
    for i, page in enumerate(pages):
        page.click("#fetchbtn")
        t = wait_text(page, "#fetch", lambda s: "fetch 200" in s, 15)
        check(f"fetch_client{i}", "fetch 200" in t, t)
    # reload keeps state (Redis / memory manager)
    pages[0].reload(wait_until="load")
    t = wait_text(pages[0], "#count", lambda s: "count: 2" in s, 15)
    check("reload_keeps_count", "count: 2" in t, t)
    if shots:
        os.makedirs(shots, exist_ok=True)
        pages[0].screenshot(path=os.path.join(shots, f"{label}-client0.png"))
    for i, e in enumerate(logs):
        bad = e["console"] + e["errors"] + e["failed"] + e["http_err"]
        check(f"console_clean_client{i}", not bad, " | ".join(bad)[:400])
    browser.close()
res = {"label": label, "base": base, "clients": N, "checks": checks, "tokens": tokens, "socket_pids": pids, "poke_pids": poke_pids,
       "pass": sum(c["ok"] for c in checks), "fail": sum(not c["ok"] for c in checks), "logs": logs}
json.dump(res, open(out, "w"), indent=1)
print(f"== {label}: pass={res['pass']} fail={res['fail']}")
