"""Chromium driver: #7412/#7696 (raise mid-yield, supersedes), disconnect mid-event, #7738 linked get_state fail/cancel,
bg task across navigation. Usage: $SB/envs/driver/bin/python drive_cancel.py BASE OUT_JSON SHOTS_DIR [--no-cancel]"""
import json, sys, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

assert "/envs/driver/" in sys.executable, sys.executable
base, out, shots = sys.argv[1].rstrip("/"), Path(sys.argv[2]), Path(sys.argv[3])
shots.mkdir(parents=True, exist_ok=True)
R = {"checks": {}, "console": [], "failed_requests": []}
IDS = ["count", "bg_count", "sup_calls", "sup_progress", "sup_done", "r1", "r2", "linked", "other_v", "slow_done"]


def api(path, method="GET"):
    req = urllib.request.Request(base + path, method=method)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def vals(page):
    return {i: page.inner_text(f"#{i}") for i in IDS}


def check(name, ok, **kw):
    R["checks"][name] = {"ok": bool(ok), **kw}
    print(("PASS " if ok else "FAIL ") + name, json.dumps(kw)[:400], flush=True)


def wait_text(page, sel, pred, timeout=15):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        v = page.inner_text(sel)
        if pred(v):
            return time.monotonic() - t0, v
        time.sleep(0.05)
    return None, page.inner_text(sel)


def new_page(ctx):
    page = ctx.new_page()
    page.on("console", lambda m: R["console"].append(f"{m.type}: {m.text[:300]}") if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: R["console"].append(f"PAGEERROR {str(e)[:300]}"))
    page.on("requestfailed", lambda r: R["failed_requests"].append(f"{r.url} {r.failure}"))
    page.on("response", lambda r: R["failed_requests"].append(f"{r.status} {r.url}") if r.status >= 400 else None)
    page.goto(base + "/", wait_until="networkidle", timeout=120000)
    page.wait_for_function("() => document.querySelector('#count') !== null", timeout=60000)
    time.sleep(1.0)
    return page


with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    page = new_page(ctx)
    tok = page.evaluate("() => sessionStorage.getItem('token')")
    R["token"] = tok
    # 1. raise mid-yield: r1 (before yield) and r2 (after last yield) kept and shown
    page.click("#raise")
    dt, v = wait_text(page, "#r2", lambda x: x == "1", 5)
    srv = api(f"/api/get?token={tok}")
    page.screenshot(path=str(shots / "01_raise.png"))
    check("raise_mid_ui", page.inner_text("#r1") == "1" and v == "1", ui=vals(page), server={k: srv[k] for k in ("r1", "r2")})
    check("raise_mid_server", srv["r1"] == 1 and srv["r2"] == 1, server={k: srv[k] for k in ("r1", "r2")})
    # 2. supersedes: second call cancels the first; progress of the first kept
    page.click("#sup")
    time.sleep(0.75)
    page.click("#sup")
    time.sleep(3.0)
    srv = api(f"/api/get?token={tok}")
    ui = vals(page)
    page.screenshot(path=str(shots / "02_sup.png"))
    check("supersedes_ui_matches_server", all(str(srv[k]) == ui[k] for k in ("sup_calls", "sup_progress", "sup_done")),
          ui={k: ui[k] for k in ("sup_calls", "sup_progress", "sup_done")}, server={k: srv[k] for k in ("sup_calls", "sup_progress", "sup_done")})
    check("supersedes_first_progress_kept", srv["sup_calls"] == 2 and srv["sup_progress"] >= 6 and srv["sup_done"] == 1,
          server={k: srv[k] for k in ("sup_calls", "sup_progress", "sup_done")})
    # 3. reload: server state shown
    page.reload(wait_until="networkidle"); time.sleep(1.5)
    ui2 = vals(page)
    check("reload_keeps", ui2["r2"] == "1" and ui2["sup_progress"] == str(srv["sup_progress"]), ui=ui2)
    # 4. #7738 linked get_state failure (task then ends without touching self), next event latency
    def linked_result(want, timeout=15):
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout:
            for _ in range(4):  # several workers: ask until the task's worker answers
                r = api(f"/api/linked?token={tok}")
                if r["result"] and r["result"]["status"] != "entering" and r["result"]["mode"] == want:
                    return r
            time.sleep(0.2)
        return r
    page.click("#linked_fail")
    lr = linked_result("fail")
    time.sleep(0.5)
    c0 = int(page.inner_text("#count"))
    page.click("#incr")
    dt2, v2 = wait_text(page, "#count", lambda x: x == str(c0 + 1), 30)
    check("linked_fail_then_event", lr["result"]["status"].startswith("error") and dt2 is not None and dt2 < 2.0, linked=lr, next_event_s=dt2, count=v2)
    # 5. #7738 linked cancel during load (redis paused 3 s inside the parent's unpickle), then next event
    if "--no-cancel" not in sys.argv:
        page.click("#linked_cancel")
        dt, v = wait_text(page, "#linked", lambda x: x.startswith("start:cancel"), 10)
        time.sleep(0.8)
        cancelled = None
        for i in range(12):
            try:
                r = api(f"/api/cancel?token={tok}", "POST")
            except Exception as e:  # noqa: BLE001
                r = {"err": repr(e)}
            if r.get("cancelled"):
                cancelled = r; break
        t_cancel = time.monotonic()
        lr = linked_result("cancel")
        time.sleep(max(0, 3.2 - (time.monotonic() - t_cancel)))
        c0 = int(page.inner_text("#count"))
        page.click("#incr")
        dt2, v2 = wait_text(page, "#count", lambda x: x == str(c0 + 1), 30)
        check("linked_cancel_then_event", cancelled is not None and lr["result"]["status"] == "cancelled" and lr["result"].get("paused_at") and dt2 is not None and dt2 < 2.0,
              cancelled=cancelled, linked=lr, next_event_s=dt2, since_cancel_s=round(time.monotonic() - t_cancel, 2))
    # 6. linked ok still works
    page.click("#linked_ok")
    dt, v = wait_text(page, "#linked", lambda x: x == "ok:ok", 15)
    check("linked_ok", v == "ok:ok", linked=v, s=dt)
    # 7. bg task across navigation
    c0 = int(page.inner_text("#count")); b0 = int(page.inner_text("#bg_count"))
    page.click("#bg"); time.sleep(0.3)
    page.click("#nav_other"); time.sleep(0.5); page.click("#nav_home")
    dt, v = wait_text(page, "#bg_count", lambda x: x == str(b0 + 50), 20)
    check("bg_across_nav", v == str(b0 + 50) and page.inner_text("#count") == str(c0 + 50), bg=v, count=page.inner_text("#count"))
    # 8. disconnect mid-event: slow(3s) then close the tab; reopen same token
    s0 = int(page.inner_text("#slow_done"))
    page.click("#slow"); time.sleep(0.5)
    page.close()
    time.sleep(4.0)
    ctx2 = b.new_context()
    ctx2.add_init_script(f"window.sessionStorage.setItem('token', {json.dumps(tok)});")
    page = new_page(ctx2)
    srv = api(f"/api/get?token={tok}")
    c0 = int(page.inner_text("#count"))
    page.click("#incr")
    dt2, v2 = wait_text(page, "#count", lambda x: x == str(c0 + 1), 30)
    check("disconnect_mid_event", page.evaluate("() => sessionStorage.getItem('token')") == tok and dt2 is not None and dt2 < 2.0,
          slow_done_server=srv["slow_done"], slow_done_before=s0, next_event_s=dt2)
    page.screenshot(path=str(shots / "08_final.png"))
    b.close()
R["console"] = [c for c in R["console"] if "Hey developer" not in c]
out.write_text(json.dumps(R, indent=1))
print("console:", R["console"][:10]); print("failed:", R["failed_requests"][:10])
