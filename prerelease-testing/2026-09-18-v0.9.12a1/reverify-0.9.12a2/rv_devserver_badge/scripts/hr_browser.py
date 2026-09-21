"""Hot-reload end-to-end in a held-open browser + syntax-error recovery.

usage: hr_browser.py <frontend_url> <backend_url> <appfile> <shots> <outjson>
Run with the driver venv python.
"""
import json, socket, sys, time, urllib.request
from playwright.sync_api import sync_playwright

FE, BE, APPFILE, SHOTS, OUT = sys.argv[1:6]
orig = open(APPFILE).read()
res = {}
cons, perr, failed, http45 = [], [], [], []


def raw_ping(port, tmo=6):
    t = time.time()
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=tmo)
        s.sendall(b"GET /ping HTTP/1.1\r\nHost: l\r\nConnection: close\r\n\r\n")
        d = s.recv(100)
        s.close()
        out = d.split(b" ")[1].decode() if d.startswith(b"HTTP") else "ODD"
    except ConnectionRefusedError:
        out = "CONNECTION_REFUSED"
    except socket.timeout:
        out = f"TIMEOUT_NO_REPLY_{tmo}s"
    except Exception as e:
        out = type(e).__name__
    return [out, round(time.time() - t, 2)]


BPORT = int(BE.rsplit(":", 1)[1])
try:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        pg = b.new_context(viewport={"width": 1280, "height": 900}).new_page()
        pg.on("console", lambda m: cons.append((m.type, m.text[:200])))
        pg.on("pageerror", lambda e: perr.append(str(e)[:200]))
        pg.on("requestfailed", lambda r: failed.append((r.url[:120], str(r.failure)[:80])))
        pg.on("response", lambda r: http45.append((r.url[:120], r.status)) if r.status >= 400 else None)
        pg.goto(FE, wait_until="networkidle", timeout=90000)
        pg.wait_for_timeout(2500)
        res["heading_before"] = pg.locator("#heading").inner_text() if pg.locator("#heading").count() else pg.locator("h1,h2,h3").first.inner_text()
        # exercise state: click the increment button
        btn = pg.get_by_role("button", name="inc")
        if btn.count():
            btn.first.click(); pg.wait_for_timeout(600)
        res["body_before"] = pg.inner_text("body")[:400]
        pg.screenshot(path=f"{SHOTS}/hr-before.png")

        # --- harmless hot reload
        open(APPFILE, "w").write(orig.replace('HEADING = "dsc v5-reload"', 'HEADING = "dsc v6-HOTRELOAD"'))
        t0 = time.time()
        pings = []
        got = None
        while time.time() - t0 < 75:
            pings.append(raw_ping(BPORT, 4))
            try:
                txt = pg.inner_text("body")
            except Exception:
                txt = ""
            if "v6-HOTRELOAD" in txt:
                got = round(time.time() - t0, 1)
                break
            pg.wait_for_timeout(1000)
        res["hot_reload_seen_in_browser_after_s"] = got
        res["backend_pings_during_reload"] = pings
        res["backend_never_hung"] = all(pp[0] != "TIMEOUT_NO_REPLY_4s" for pp in pings)
        res["body_after_reload"] = pg.inner_text("body")[:400] if got else None
        pg.screenshot(path=f"{SHOTS}/hr-after.png")
        # state still works after reload
        btn = pg.get_by_role("button", name="inc")
        if btn.count():
            btn.first.click(); pg.wait_for_timeout(800)
            res["body_after_reload_click"] = pg.inner_text("body")[:400]

        # --- syntax error saved mid-run
        open(APPFILE, "w").write(orig + "\n\ndef broken(:\n    pass\n")
        time.sleep(12)
        res["ping_after_syntax_error_12s"] = raw_ping(BPORT)
        time.sleep(8)
        res["ping_after_syntax_error_20s"] = raw_ping(BPORT)
        # --- fix it
        open(APPFILE, "w").write(orig)
        t0 = time.time()
        rec = None
        while time.time() - t0 < 90:
            pp = raw_ping(BPORT, 4)
            if pp[0] == "200":
                rec = round(time.time() - t0, 1)
                break
            time.sleep(2)
        res["recovered_to_200_after_s"] = rec
        pg.reload(wait_until="networkidle", timeout=90000)
        pg.wait_for_timeout(2000)
        res["body_after_fix"] = pg.inner_text("body")[:400]
        pg.screenshot(path=f"{SHOTS}/hr-recovered.png")
        b.close()
finally:
    open(APPFILE, "w").write(orig)

res["console"] = cons
res["page_errors"] = perr
res["failed_requests"] = failed
res["http_4xx_5xx"] = http45
print(json.dumps(res, indent=1)[:4000])
json.dump(res, open(OUT, "w"), indent=1)
