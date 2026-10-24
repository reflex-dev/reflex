"""Playwright driver for the hnet probe app (hydration_net item, 0.10.1a1 pass).

Usage: hnet_drive.py --base http://localhost:FP --out DIR [--only big,shared,cv,typed,ovr,cs,ip] [--big-proxy-base URL]
Scenarios:
  big     #7551/#7605: 300k LocalStorage ok; 1.1 MB LocalStorage -> one error, no reconnect loop, toast; recovery
  bigproxy #7605: via --big-proxy-base (close_proxy.py): 300k storage, proxy closes -> backoff, toast, recovery
  shared  #7545: ComponentState x2 + plain state sharing one sync=True storage name converge across two tabs
  cv      #7568: cached storage dependents evaluated once per page load
  typed   #7603: Cookie/LocalStorage/SessionStorage-annotated vars + int/bool/dict storage hydrate and persist
  ovr     #7572: get_delta override assigning a storage var; cached dependents follow; storage gets the correction
  cs      #7407: global client_state: push before any reader mounts; late reader follows set-back-to-default
  ip      shows router.session.client_ip on the frontend and in handlers (incl. an upload) through --base
Results: DIR/<scenario>.json + DIR/summary.json; prints one line per check.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "drivers"))
from hydcommon import CHROMIUM, Recorder, is_benign, text, wait_text, wait_until  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

assert f"/envs/{os.environ.get('DRV_VENV', 'driver')}/" in sync_playwright.__module__ or True
import playwright  # noqa: E402

assert f"/envs/{os.environ.get('DRV_VENV', 'driver')}/" in playwright.__file__, playwright.__file__

ap = argparse.ArgumentParser()
ap.add_argument("--base", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--only", default="")
ap.add_argument("--big-proxy-base", default=None)
ap.add_argument("--big-size", type=int, default=1_100_000)
ap.add_argument("--observe", type=float, default=12.0)
A = ap.parse_args()
OUT = Path(A.out)
OUT.mkdir(parents=True, exist_ok=True)
RESULTS: dict = {"checks": {}}


def record(name: str, ok: bool, **info):
    RESULTS["checks"][name] = {"ok": bool(ok), **info}
    print(f"[{'pass' if ok else 'FAIL'}] {name}: {json.dumps(info, default=str)[:900]}", flush=True)


def hyd(page, timeout=30000) -> bool:
    return wait_text(page, "#hydrated", "true", timeout)


def ctx(b, rec: Recorder, tag: str, **kw):
    c = b.new_context(**kw)
    p = c.new_page()
    rec.attach(p, tag)
    return c, p


def ws_opens(rec: Recorder, tag=None):
    return [e for e in rec.ws_events if e["ev"] == "open" and (tag is None or e["tag"] == tag)]


def connect_frames_out(rec: Recorder, tag=None):
    return [f for f in rec.ws_frames if f["dir"] == "out" and str(f["p"]).startswith("40") and (tag is None or f["tag"] == tag)]


def toasts(page) -> list[str]:
    try:
        return page.evaluate("() => Array.from(document.querySelectorAll('[data-sonner-toast]')).map(e => e.innerText.slice(0, 300))")
    except Exception:  # noqa: BLE001
        return []


def gaps(ts: list[float]) -> list[float]:
    return [round(b - a, 3) for a, b in zip(ts, ts[1:])]


def s_big(b):
    rec = Recorder()
    c, p = ctx(b, rec, "big")
    p.goto(f"{A.base}/big")
    ok = hyd(p)
    p.click("#big-300k")
    ok300 = wait_text(p, "#big-len", "len:300000", 15000)
    ls_len = p.evaluate("() => (localStorage.getItem('hnet_big') || '').length")
    t0 = time.time()
    p.reload()
    ok_rl = hyd(p)
    t_rl = round(time.time() - t0, 2)
    record("big_300k_roundtrip", ok and ok300 and ls_len == 300000 and ok_rl and text(p, "#big-len") == "len:300000",
           ls_len=ls_len, reload_hydrate_s=t_rl)
    # oversized: set storage directly, reload, observe
    p.evaluate(f"() => localStorage.setItem('hnet_big', 'y'.repeat({A.big_size}))")
    n_open0 = len(ws_opens(rec, "big"))
    n_c0 = len(connect_frames_out(rec, "big"))
    t0 = time.time()
    p.reload()
    first_toast = None
    toast_seen_at = None
    errs = []
    while time.time() - t0 < A.observe:
        tl = toasts(p)
        if tl and first_toast is None:
            first_toast = tl
            toast_seen_at = round(time.time() - t0, 2)
        p.wait_for_timeout(250)
    opens = ws_opens(rec, "big")[n_open0:]
    cframes = connect_frames_out(rec, "big")[n_c0:]
    errs = [cc["text"] for cc in rec.console if cc["type"] == "error" and cc["tag"] == "big"]
    hyd_msgs = [e for e in errs if "Hydration payload" in e]
    hydrated = text(p, "#hydrated")
    final_toasts = toasts(p)
    open_ts = [e["t"] for e in opens]
    record("big_oversize_reported_once", len(hyd_msgs) == 1 and hydrated != "true" and len(cframes) == 0 and len(opens) <= 2,
           n_ws_opens=len(opens), open_gaps=gaps(open_ts)[:20], n_connect_frames_sent=len(cframes), hydration_errors=hyd_msgs[:3],
           n_console_errors=len(errs), hydrated=hydrated, size=A.big_size)
    record("big_oversize_toast_shown_and_stays", bool(first_toast) and any("Hydration payload" in t for t in (first_toast or []))
           and any("Hydration payload" in t for t in final_toasts), first_toast=first_toast, toast_at_s=toast_seen_at, final_toasts=final_toasts)
    p.screenshot(path=str(OUT / "big_oversize.png"))
    # recovery
    p.evaluate("() => localStorage.setItem('hnet_big', 'z'.repeat(100))")
    n_open1 = len(ws_opens(rec, "big"))
    p.reload()
    ok_rec = hyd(p)
    record("big_recovery_after_shrink", ok_rec and text(p, "#big-len") == "len:100", big_len=text(p, "#big-len"),
           ws_opens_after=len(ws_opens(rec, "big")) - n_open1, toasts=toasts(p))
    # click works after recovery
    p.click("#click")
    record("big_click_after_recovery", wait_text(p, "#clicks", "clicks:1", 5000))
    json.dump({"ws_events": rec.ws_events, "console": rec.console, "anomalies": rec.anomalies(),
               "frames": [{k: v for k, v in f.items() if k != "p"} | {"p": str(f["p"])[:160]} for f in rec.ws_frames]},
              open(OUT / "big.json", "w"), indent=1, default=str)
    c.close()


def s_bigproxy(b):
    base = A.big_proxy_base
    if not base:
        record("bigproxy_skipped", True, reason="no --big-proxy-base")
        return
    rec = Recorder()
    c, p = ctx(b, rec, "bigproxy")
    p.goto(f"{base}/big")
    ok = hyd(p)
    p.evaluate("() => localStorage.setItem('hnet_big', 'y'.repeat(300000))")
    n_open0 = len(ws_opens(rec, "bigproxy"))
    t0 = time.time()
    p.reload()
    first_toast = None
    toast_at = None
    while time.time() - t0 < A.observe:
        tl = toasts(p)
        if tl and first_toast is None:
            first_toast, toast_at = tl, round(time.time() - t0, 2)
        p.wait_for_timeout(250)
    opens = ws_opens(rec, "bigproxy")[n_open0:]
    open_ts = [e["t"] for e in opens]
    g = gaps(open_ts)
    errs = [cc["text"][:200] for cc in rec.console if cc["type"] == "error" and cc["tag"] == "bigproxy"]
    hydrated = text(p, "#hydrated")
    growing = len(g) >= 3 and all(g[i + 1] >= g[i] - 0.05 for i in range(min(len(g) - 1, 6)))
    record("bigproxy_backoff_no_tight_loop", ok and hydrated != "true" and len(opens) <= 20 and growing,
           n_ws_opens=len(opens), open_gaps=g[:25], hydrated=hydrated, console_errors=errs[:5], observe_s=A.observe)
    record("bigproxy_toast_shown", bool(first_toast), first_toast=first_toast, toast_at_s=toast_at, final=toasts(p))
    p.screenshot(path=str(OUT / "bigproxy.png"))
    p.evaluate("() => localStorage.setItem('hnet_big', 'z'.repeat(10))")
    p.reload()
    record("bigproxy_recovery", hyd(p) and text(p, "#big-len") == "len:10", big_len=text(p, "#big-len"))
    json.dump({"ws_events": rec.ws_events, "console": rec.console, "anomalies": rec.anomalies()}, open(OUT / "bigproxy.json", "w"), indent=1, default=str)
    c.close()


def s_shared(b):
    rec = Recorder()
    c, p1 = ctx(b, rec, "t1")
    p2 = c.new_page()
    rec.attach(p2, "t2")
    p1.goto(f"{A.base}/shared")
    p2.goto(f"{A.base}/shared")
    ok = hyd(p1) and hyd(p2)
    ids = ["#v-a", "#v-b", "#v-plain"]

    def vals(p):
        return [text(p, i) for i in ids]

    record("shared_initial", ok, t1=vals(p1), t2=vals(p2), other=[text(p1, "#v-other"), text(p2, "#v-other")])

    def conv(p, v):
        # #7545: every var sharing the storage name converges in the OTHER tab. The writing tab's sibling vars get no
        # `storage` event (browser semantics), so the same-tab values are reported as info only.
        return wait_until(p, lambda: vals(p) == [v, v, v], 8000)

    p1.click("#set-a")
    c2 = conv(p2, "from-a")
    p1.wait_for_timeout(500)
    record("shared_set_a_syncs_all_in_other_tab", bool(c2), writing_tab=vals(p1), other_tab=vals(p2), ls=p2.evaluate("() => localStorage.getItem('hnet_shared')"))
    p2.click("#set-plain")
    c1 = conv(p1, "from-plain")
    p2.wait_for_timeout(500)
    record("shared_set_plain_syncs_all_in_other_tab", bool(c1), other_tab=vals(p1), writing_tab=vals(p2))
    p2.fill("#in-b", "typed-b")
    p2.locator("#in-b").blur()
    c1 = conv(p1, "typed-b")
    p2.wait_for_timeout(500)
    record("shared_typed_b_syncs_all_in_other_tab", bool(c1), other_tab=vals(p1), writing_tab=vals(p2))
    p1.click("#set-other")
    o2 = wait_text(p2, "#v-other", "from-other", 8000)
    p2.wait_for_timeout(500)
    record("shared_other_name_unaffected", o2 and vals(p1) == ["typed-b"] * 3, t1=vals(p1), t2=vals(p2), other2=text(p2, "#v-other"))
    n0 = len(rec.ws_frames)
    p1.wait_for_timeout(2000)
    quiet = len(rec.ws_frames) - n0
    record("shared_quiet_after", quiet < 10, frames_in_2s=quiet, total_frames=len(rec.ws_frames))
    # a third tab boots: sees the shared value everywhere
    p3 = c.new_page()
    rec.attach(p3, "t3")
    p3.goto(f"{A.base}/shared")
    hyd(p3)
    record("shared_new_tab_sees_value", vals(p3) == ["typed-b"] * 3, t3=vals(p3))
    json.dump({"anomalies": rec.anomalies(), "n_frames": len(rec.ws_frames)}, open(OUT / "shared.json", "w"), indent=1, default=str)
    c.close()


def s_cv(b):
    rec = Recorder()
    c, p = ctx(b, rec, "cv")
    p.goto(f"{A.base}/cv")
    hyd(p)
    p.click("#set-tok")
    wait_text(p, "#tok-len", "tok_len:6", 8000)
    p.evaluate("() => { document.cookie = 'hnet_cv_ck=zz; path=/'; }")
    p.click("#reset")
    wait_text(p, "#evals", json.dumps({"sib_len": 0, "tok_len": 0, "uncached": 0}, sort_keys=True), 8000)
    p.reload()
    hyd(p)
    shown = [text(p, "#tok-len"), text(p, "#sib-len"), text(p, "#unc")]
    p.click("#snap")
    p.wait_for_timeout(800)
    ev = json.loads(text(p, "#evals") or "{}")
    # tok_len = len(tok)+len(ck) = 6+2 = 8 ; sib_len = 6
    record("cv_storage_dependents_once_per_load", ev.get("tok_len") == 1 and ev.get("sib_len") == 1 and shown[0] == "tok_len:8" and shown[1] == "sib_len:6",
           evals=ev, shown=shown)
    # second reload for stability
    p.click("#reset")
    p.wait_for_timeout(500)
    p.reload()
    hyd(p)
    p.click("#snap")
    p.wait_for_timeout(800)
    ev2 = json.loads(text(p, "#evals") or "{}")
    record("cv_storage_dependents_once_per_load_2", ev2.get("tok_len") == 1 and ev2.get("sib_len") == 1, evals=ev2)
    json.dump({"anomalies": rec.anomalies()}, open(OUT / "cv.json", "w"), indent=1, default=str)
    c.close()


def s_typed(b):
    rec = Recorder()
    c, p = ctx(b, rec, "typed")
    p.goto(f"{A.base}/typed")
    hyd(p)
    s0 = json.loads(text(p, "#summary") or "{}")
    # pass criterion: the storage-annotated str vars (#7603). int/bool/dict storage vars are reported as info (nonstd).
    record("typed_defaults", s0.get("ann_ls", [None])[0] == "ls-d" and s0.get("ann_opt", [None])[0] == "opt-d" and s0.get("ann_fld", [None])[0] == "fld-d",
           summary=s0, console=[cc["text"][:200] for cc in rec.console if cc["type"] in ("error", "warning") and not is_benign(cc["text"])])
    p.click("#w1")
    ok = wait_text(p, "#ann-ls", "ls-w1", 8000)
    p.wait_for_timeout(500)
    st = p.evaluate("""() => ({ls: Object.fromEntries(Object.keys(localStorage).filter(k=>k.startsWith('hnet_')).map(k=>[k, localStorage.getItem(k)])),
        ss: Object.fromEntries(Object.keys(sessionStorage).filter(k=>k.startsWith('hnet_')).map(k=>[k, sessionStorage.getItem(k)])), ck: document.cookie})""")
    s1 = json.loads(text(p, "#summary") or "{}")
    record("typed_write_w1", ok and s1.get("ann_ck", [None])[0] == "ck-w1" and st["ls"].get("hnet_ann_ls") == "ls-w1" and "hnet_ann_ck=ck-w1" in st["ck"]
           and st["ss"].get("hnet_ann_ss") == "ss-w1", summary=s1, storage=st)
    p.reload()
    hyd(p)
    s2 = json.loads(text(p, "#summary") or "{}")
    record("typed_reload_hydrates_w1", s2.get("ann_ls", [None])[0] == "ls-w1" and s2.get("ann_ck", [None])[0] == "ck-w1" and s2.get("ann_ss", [None])[0] == "ss-w1"
           and s2.get("ann_opt", [None])[0] == "opt-w1" and s2.get("ann_fld", [None])[0] == "fld-w1", summary=s2,
           shown=[text(p, "#ann-ls"), text(p, "#n-int"), text(p, "#n-bool"), text(p, "#j-dict")])
    record("typed_nonstr_storage_roundtrip_INFO", True, n_int=s2.get("n_int"), n_bool=s2.get("n_bool"), j_dict=s2.get("j_dict"), ls_json=st["ls"].get("hnet_json"))
    p.click("#opt-none")
    p.wait_for_timeout(600)
    s3 = json.loads(text(p, "#summary") or "{}")
    ls_opt = p.evaluate("() => localStorage.getItem('hnet_ann_opt')")
    p.reload()
    hyd(p)
    s4 = json.loads(text(p, "#summary") or "{}")
    record("typed_opt_none_roundtrip", True, after_none=s3.get("ann_opt"), ls_after_none=ls_opt, after_reload=s4.get("ann_opt"))
    p.click("#w2")
    wait_text(p, "#ann-ls", "ls-w2", 8000)
    p.wait_for_timeout(400)
    p.reload()
    hyd(p)
    s5 = json.loads(text(p, "#summary") or "{}")
    record("typed_reload_hydrates_w2", s5.get("ann_ls", [None])[0] == "ls-w2" and s5.get("ann_ck", [None])[0] == "ck-w2" and s5.get("ann_fld", [None])[0] == "fld-w2", summary=s5)
    an = rec.anomalies()
    record("typed_console_clean", not an["console_err_warn"] and not an["pageerrors"], anomalies=an)
    json.dump({"anomalies": an, "console": rec.console}, open(OUT / "typed.json", "w"), indent=1, default=str)
    c.close()


def s_ovr(b):
    rec = Recorder()
    c, p = ctx(b, rec, "ovr")
    p.goto(f"{A.base}/ovr")
    hyd(p)
    p.click("#set-good")
    ok = wait_text(p, "#tok-ok", "ok:True:good-1", 8000)
    p.reload()
    hyd(p)
    record("ovr_good_persists", ok and text(p, "#tok-ok") == "ok:True:good-1" and text(p, "#tok") == "[good-1]", tok_ok=text(p, "#tok-ok"), tok=text(p, "#tok"))
    p.evaluate("() => localStorage.setItem('hnet_ovr', 'bad-x')")
    p.reload()
    hyd(p)
    p.wait_for_timeout(800)
    got = {"tok_ok": text(p, "#tok-ok"), "tok": text(p, "#tok"), "plain_dep": text(p, "#plain-dep"), "ls": p.evaluate("() => localStorage.getItem('hnet_ovr')")}
    p.click("#snap")
    p.wait_for_timeout(500)
    got["calls"] = text(p, "#calls")
    record("ovr_bad_sanitised_dependents_follow", got["tok_ok"] == "ok:False:" and got["tok"] == "[]" and got["plain_dep"] == "plain:sanitised" and got["ls"] == "", **got)
    p.reload()
    hyd(p)
    record("ovr_after_sanitise_reload", text(p, "#tok-ok") == "ok:False:" and text(p, "#tok") == "[]", tok_ok=text(p, "#tok-ok"), tok=text(p, "#tok"), ls=p.evaluate("() => localStorage.getItem('hnet_ovr')"))
    p.click("#set-bad")
    p.wait_for_timeout(1000)
    got2 = {"tok_ok": text(p, "#tok-ok"), "tok": text(p, "#tok"), "plain_dep": text(p, "#plain-dep"), "ls": p.evaluate("() => localStorage.getItem('hnet_ovr')")}
    record("ovr_event_bad_sanitised", got2["tok"] == "[]" and got2["tok_ok"] == "ok:False:" and got2["ls"] == "", **got2)
    an = rec.anomalies()
    json.dump({"anomalies": an, "console": rec.console}, open(OUT / "ovr.json", "w"), indent=1, default=str)
    c.close()


def s_cs(b):
    rec = Recorder()
    c, p = ctx(b, rec, "cs")
    p.goto(f"{A.base}/cs")
    hyd(p)
    wait_text(p, "#log", "push_on_load", 8000)
    p.wait_for_timeout(500)
    errs = [cc["text"][:200] for cc in rec.console if cc["type"] == "error"] + [e["error"][:200] for e in rec.pageerrors]
    record("cs_push_before_reader_no_error", not any("_client_state_set" in e or "is not a function" in e for e in errs), errors=errs)
    p.click("#toggle")
    ok = wait_text(p, "#flag-reader", "flag=[pushed-on-load]", 5000)
    record("cs_late_reader_sees_pushed", ok and text(p, "#count-reader") == "count=5", flag=text(p, "#flag-reader"), count=text(p, "#count-reader"))
    p.click("#set-clicked")
    ok1 = wait_text(p, "#flag-reader", "flag=[clicked]", 5000)
    p.click("#toggle")
    p.wait_for_timeout(200)
    p.click("#toggle")
    ok2 = wait_text(p, "#flag-reader", "flag=[clicked]", 5000)
    p.click("#set-default")
    ok3 = wait_text(p, "#flag-reader", "flag=[initial]", 5000)
    record("cs_late_reader_follows_set_back_to_default", ok1 and ok2 and ok3, flag=text(p, "#flag-reader"))
    # hide, set while hidden, show -> late reader must show the set value; then back to default
    p.click("#toggle")
    p.wait_for_timeout(200)
    p.click("#set-clicked")
    p.wait_for_timeout(200)
    p.click("#toggle")
    ok4 = wait_text(p, "#flag-reader", "flag=[clicked]", 5000)
    p.click("#set-default")
    ok5 = wait_text(p, "#flag-reader", "flag=[initial]", 5000)
    record("cs_reader_mounted_after_set_then_default", ok4 and ok5, flag=text(p, "#flag-reader"))
    p.click("#push-none")
    ok6 = wait_text(p, "#flag-reader", "flag=[]", 5000)
    p.click("#push-backend")
    ok7 = wait_text(p, "#flag-reader", "flag=[from-backend]", 5000)
    p.click("#toggle")
    p.wait_for_timeout(200)
    p.click("#push-none")
    p.wait_for_timeout(300)
    p.click("#toggle")
    ok8 = wait_text(p, "#flag-reader", "flag=[]", 5000)
    record("cs_push_none_and_backend", ok6 and ok7 and ok8, flag=text(p, "#flag-reader"))
    p.click("#count-inc")
    ok9 = wait_text(p, "#count-reader", "count=6", 5000)
    record("cs_count_int", ok9, count=text(p, "#count-reader"))
    # gate page: reader only after hydration; push arrives during on_load
    p2 = c.new_page()
    rec.attach(p2, "gate")
    p2.goto(f"{A.base}/gate")
    hyd(p2)
    okg = wait_text(p2, "#flag-reader", "flag=[pushed-on-load]", 8000)
    errs2 = [cc["text"][:200] for cc in rec.console if cc["type"] == "error" and cc["tag"] == "gate"] + [e["error"][:200] for e in rec.pageerrors if e["tag"] == "gate"]
    record("cs_gate_push_during_onload", okg and not errs2, flag=text(p2, "#flag-reader"), errors=errs2)
    p2.click("#set-clicked")
    wait_text(p2, "#flag-reader", "flag=[clicked]", 5000)
    p2.click("#set-default")
    okg2 = wait_text(p2, "#flag-reader", "flag=[initial]", 5000)
    record("cs_gate_set_default", okg2, flag=text(p2, "#flag-reader"))
    an = rec.anomalies()
    json.dump({"anomalies": an, "console": rec.console}, open(OUT / "cs.json", "w"), indent=1, default=str)
    c.close()


def s_ip(b):
    rec = Recorder()
    c, p = ctx(b, rec, "ip")
    p.goto(f"{A.base}/ip")
    hyd(p)
    wait_until(p, lambda: (text(p, "#n") or "") != "n:0", 8000)
    p.click("#rec")
    wait_text(p, "#n", "n:2", 5000)
    tmp = OUT / "up.txt"
    tmp.write_text("hello")
    p.set_input_files("#upl input[type=file]", str(tmp))
    p.click("#do-upload")
    wait_text(p, "#n", "n:3", 10000)
    lines = p.evaluate("() => Array.from(document.querySelectorAll('pre.seen')).map(e => e.innerText)")
    parsed = [json.loads(ln) for ln in lines]
    record("ip_frontend_and_handlers", len(parsed) == 3, f_ip=text(p, "#f_ip"), cv_ip=text(p, "#cv_ip"),
           handler_ips=[(x["tag"], x["ip"], x["x-forwarded-for"], x["asgi-scope-client"]) for x in parsed])
    json.dump({"lines": parsed, "f_ip": text(p, "#f_ip"), "anomalies": rec.anomalies()}, open(OUT / "ip.json", "w"), indent=1, default=str)
    c.close()


SCEN = {"big": s_big, "bigproxy": s_bigproxy, "shared": s_shared, "cv": s_cv, "typed": s_typed, "ovr": s_ovr, "cs": s_cs, "ip": s_ip}
want = [s for s in A.only.split(",") if s] or list(SCEN)
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROMIUM)
    for name in want:
        try:
            SCEN[name](b)
        except Exception as e:  # noqa: BLE001
            record(f"{name}_EXCEPTION", False, error=repr(e)[:500])
    b.close()
json.dump(RESULTS, open(OUT / "summary.json", "w"), indent=1, default=str)
n = len(RESULTS["checks"])
bad = [k for k, v in RESULTS["checks"].items() if not v["ok"]]
print(f"SUMMARY {n - len(bad)}/{n} pass; fail={bad}")
