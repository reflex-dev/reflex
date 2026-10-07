"""Hydration cluster scenario driver.

Usage (driver venv, client-side proxy bypass):
  NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
    $SB/envs/driver/bin/python hyd_driver.py --base http://localhost:3220 --label alpha-dev \
    --out $SB/apps/hydration/results/alpha-dev [--only s1,s2]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hydcommon import (  # noqa: E402
    CHROMIUM,
    TIMELINE_JS,
    Recorder,
    jtext,
    save_json,
    series,
    storage_dump,
    summarize_frames,
    text,
    timeline,
    wait_hydrated,
    wait_text,
    wait_until,
)
from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = "reflex___state____state.hydapp___hydapp____state"


class Ctx:
    def __init__(self, browser, base: str, out: Path, label: str):
        self.browser = browser
        self.base = base.rstrip("/")
        self.out = out
        self.label = label

    def context(self, rec: Recorder):
        ctx = self.browser.new_context(viewport={"width": 1200, "height": 900})
        ctx.add_init_script(TIMELINE_JS)
        return ctx

    def page(self, ctx, rec: Recorder, tag: str):
        p = ctx.new_page()
        rec.attach(p, tag)
        return p

    def shot(self, page, name: str):
        path = self.out / "shots" / f"{name}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            page.screenshot(path=str(path), full_page=True)
        except Exception as ex:  # noqa: BLE001
            return f"screenshot failed {ex}"
        return str(path)


def last_trace(page, prefix: str):
    tr = jtext(page, "#trace") or []
    hits = [t for t in tr if isinstance(t, str) and t.startswith(prefix)]
    return hits[-1] if hits else None


def s1_storage_roundtrip(c: Ctx, rec: Recorder) -> dict:
    """Set client storage of every kind, reload: restored before on_load reads them."""
    r: dict = {"checks": {}}
    ctx = c.context(rec)
    p = c.page(ctx, rec, "s1")
    p.goto(c.base + "/")
    r["hydrated_first"] = wait_hydrated(p)
    r["first_load_trace"] = last_trace(p, "index_load")
    r["storage_after_first_load"] = storage_dump(p)
    r["values_first"] = {k: text(p, "#" + k) for k in ["ls-plain", "ls-sync", "ss-val", "ck-val", "ck-int", "ck-int-plus", "ls-same", "sub-ls", "sub-ck", "sub-ss", "clean-ls", "clean-ck", "box-a-ls", "box-b-ls", "sub-uuid"]}
    # Set values through the UI (backend -> delta -> browser storage).
    p.click("#set-values")
    p.click("#set-sub")
    p.click("#box-a-btn")
    ok = wait_text(p, "#ls-plain", "ls-A") and wait_text(p, "#sub-ls", "sub-ls-S1") and wait_text(p, "#box-a-ls", "box-a-set")
    r["checks"]["ui_set_applied"] = ok
    p.wait_for_timeout(500)
    r["storage_after_set"] = storage_dump(p)
    # Also set the hash-equal LocalStorage var from JS to exactly its default value.
    p.evaluate("localStorage.setItem('hyd_same', 'same-value')")
    p.reload()
    r["hydrated_reload"] = wait_hydrated(p)
    r["values_reload"] = {k: text(p, "#" + k) for k in ["ls-plain", "ls-sync", "ss-val", "ck-val", "ls-same", "sub-ls", "sub-ck", "clean-ls", "box-a-ls", "box-b-ls", "load-count"]}
    r["reload_trace"] = last_trace(p, "index_load")
    exp = {"ls-plain": "ls-A", "ls-sync": "sync-A", "ss-val": "ss-A", "ck-val": "ck-A", "sub-ls": "sub-ls-S1", "sub-ck": "sub-ck-S1", "box-a-ls": "box-a-set", "box-b-ls": "box-default", "ls-same": "same-value"}
    r["checks"]["values_restored"] = {k: (r["values_reload"].get(k) == v) for k, v in exp.items()}
    lt = r["reload_trace"] or ""
    r["checks"]["on_load_saw_restored"] = all(s in lt for s in ["ls=ls-A", "sync=sync-A", "ss=ss-A", "ck=ck-A", "sub_ls=sub-ls-S1", "sub_ck=sub-ck-S1"])
    tl = timeline(p)
    r["timeline_reload_ls_plain"] = series(tl, "ls-plain")
    r["timeline_reload_hyd"] = series(tl, "hyd-flag")
    r["frames"] = summarize_frames(rec.ws_frames, "s1")
    r["screenshot"] = c.shot(p, "s1_after_reload")
    ctx.close()
    passed = r["hydrated_first"] and r["hydrated_reload"] and ok and all(r["checks"]["values_restored"].values()) and r["checks"]["on_load_saw_restored"]
    r["status"] = "pass" if passed else "fail"
    return r


def s1b_defaults_written(c: Ctx, rec: Recorder) -> dict:
    """Fresh context: which client-storage keys does a first load write to the browser?"""
    r: dict = {}
    ctx = c.context(rec)
    p = c.page(ctx, rec, "s1b")
    p.goto(c.base + "/")
    r["hydrated"] = wait_hydrated(p)
    p.wait_for_timeout(1500)
    st = storage_dump(p)
    r["storage_after_first_load"] = st
    ck = {kv.split("=", 1)[0]: kv.split("=", 1)[1] for kv in st["cookie"].split("; ") if "=" in kv}
    written = {
        "local": sorted(k for k in st["local"] if k.startswith(("hyd_", "reflex___state"))),
        "session": sorted(k for k in st["session"] if k != "token"),
        "cookie": sorted(ck),
    }
    r["client_storage_written_on_first_load"] = written
    r["frames"] = summarize_frames(rec.ws_frames, "s1b")
    # second fresh load in the same context (reload)
    p.reload()
    wait_hydrated(p)
    p.wait_for_timeout(800)
    r["storage_after_reload"] = storage_dump(p)
    ctx.close()
    any_written = any(written.values())
    r["status"] = "anomaly" if any_written else "pass"
    return r


def s2_sync_two_tabs(c: Ctx, rec: Recorder) -> dict:
    """Two tabs, same context: LocalStorage(sync=True) propagates; tokens differ."""
    r: dict = {}
    ctx = c.context(rec)
    a = c.page(ctx, rec, "s2a")
    a.goto(c.base + "/")
    wait_hydrated(a)
    b = c.page(ctx, rec, "s2b")
    b.goto(c.base + "/")
    wait_hydrated(b)
    r["tokens"] = [a.evaluate("sessionStorage.getItem('token')"), b.evaluate("sessionStorage.getItem('token')")]
    a.click("#set-sync-b")
    r["a_shows"] = wait_text(a, "#ls-sync", "sync-from-B")
    r["b_received_sync"] = wait_text(b, "#ls-sync", "sync-from-B", 8000)
    # JS write in tab B -> storage event in tab A
    b.evaluate("localStorage.setItem('hyd_sync', 'js-set-in-B')")
    r["a_received_js_write"] = wait_text(a, "#ls-sync", "js-set-in-B", 8000)
    # counter independence (different tokens -> different states)
    a.click("#inc")
    wait_text(a, "#counter", "1")
    b.wait_for_timeout(800)
    r["b_counter_after_a_inc"] = text(b, "#counter")
    # reload B: sync value restored from localStorage
    b.reload()
    wait_hydrated(b)
    r["b_after_reload"] = text(b, "#ls-sync")
    # close A, B keeps working
    a.close()
    b.click("#inc")
    r["b_counter_after_close_a"] = wait_until(b, lambda: text(b, "#counter"), 3000)
    # window.open duplicate shares sessionStorage token -> duplicate-tab handling
    with ctx.expect_page() as newp:
        b.evaluate("window.open(location.href, '_blank')")
    d = newp.value
    rec.attach(d, "s2dup")
    wait_hydrated(d)
    d.wait_for_timeout(1500)
    r["dup_token_initial_copy"] = r["tokens"][1]
    r["dup_token_after"] = d.evaluate("sessionStorage.getItem('token')")
    r["b_token_after"] = b.evaluate("sessionStorage.getItem('token')")
    r["dup_counter"] = text(d, "#counter")
    d.click("#inc")
    d.wait_for_timeout(800)
    r["dup_counter_after_inc"] = text(d, "#counter")
    r["b_counter_after_dup_inc"] = text(b, "#counter")
    r["frames_dup"] = summarize_frames(rec.ws_frames, "s2dup")[:6]
    # new context -> new token, own state
    ctx2 = c.context(rec)
    e = c.page(ctx2, rec, "s2new")
    e.goto(c.base + "/")
    wait_hydrated(e)
    r["new_ctx_counter"] = text(e, "#counter")
    r["new_ctx_ls_sync"] = text(e, "#ls-sync")
    ctx2.close()
    ctx.close()
    ok = (r["tokens"][0] != r["tokens"][1]) and r["a_shows"] and r["b_received_sync"] and r["a_received_js_write"] and r["b_after_reload"] == "js-set-in-B" and r["dup_token_after"] != r["b_token_after"]
    r["status"] = "pass" if ok else "fail"
    return r


def s3_clear_storage(c: Ctx, rec: Recorder) -> dict:
    """Clear all browser storage via devtools/JS then reload: defaults restored on backend too."""
    r: dict = {}
    ctx = c.context(rec)
    p = c.page(ctx, rec, "s3")
    p.goto(c.base + "/")
    wait_hydrated(p)
    p.click("#set-values")
    p.click("#set-sub")
    wait_text(p, "#ls-plain", "ls-A")
    wait_text(p, "#sub-ls", "sub-ls-S1")
    p.wait_for_timeout(300)
    tok = p.evaluate("sessionStorage.getItem('token')")
    p.evaluate("""() => { localStorage.clear(); const t = sessionStorage.getItem('token'); sessionStorage.clear(); sessionStorage.setItem('token', t); }""")
    ctx.clear_cookies()
    p.reload()
    wait_hydrated(p)
    r["same_token"] = p.evaluate("sessionStorage.getItem('token')") == tok
    r["values"] = {k: text(p, "#" + k) for k in ["ls-plain", "ls-sync", "ss-val", "ck-val", "sub-ls", "sub-ck", "clean-ls"]}
    r["trace"] = last_trace(p, "index_load")
    exp = {"ls-plain": "ls-default", "ls-sync": "sync-default", "ss-val": "ss-default", "ck-val": "ck-default", "sub-ls": "sub-ls-default", "sub-ck": "sub-ck-default"}
    r["checks"] = {k: r["values"].get(k) == v for k, v in exp.items()}
    r["on_load_saw_defaults"] = "ls=ls-default" in (r["trace"] or "") and "sub_ls=sub-ls-default" in (r["trace"] or "")
    # remove_local_storage event path (re-hydrates via initialEvents)
    p.click("#set-values")
    wait_text(p, "#ls-plain", "ls-A")
    lc0 = text(p, "#load-count")
    p.click("#rm-ls")
    r["after_remove_ls"] = wait_until(p, lambda: text(p, "#ls-plain") == "ls-default" and text(p, "#ls-plain"), 8000)
    p.wait_for_timeout(1000)
    r["load_count_before_after_remove"] = [lc0, text(p, "#load-count")]
    r["frames"] = summarize_frames(rec.ws_frames, "s3")[-8:]
    ctx.close()
    r["status"] = "pass" if all(r["checks"].values()) and r["on_load_saw_defaults"] and r["same_token"] else "fail"
    return r


def s4_wrong_type_cookie(c: Ctx, rec: Recorder) -> dict:
    """int-annotated Cookie set from JS to a non-int string."""
    r: dict = {}
    ctx = c.context(rec)
    p = c.page(ctx, rec, "s4")
    p.goto(c.base + "/")
    wait_hydrated(p)
    r["before"] = {"ck-int": text(p, "#ck-int"), "ck-int-plus": text(p, "#ck-int-plus")}
    p.evaluate("document.cookie = 'hyd_int=abc; path=/'")
    p.reload()
    r["hydrated"] = wait_hydrated(p)
    r["after"] = {"ck-int": text(p, "#ck-int"), "ck-int-plus": text(p, "#ck-int-plus")}
    p.click("#int-plus-one")
    p.wait_for_timeout(800)
    r["int_plus_one_trace"] = last_trace(p, "int_plus_one")
    p.evaluate("document.cookie = 'hyd_int=41; path=/'")
    p.reload()
    wait_hydrated(p)
    p.click("#int-plus-one")
    p.wait_for_timeout(800)
    r["numeric_cookie"] = {"ck-int": text(p, "#ck-int"), "ck-int-plus": text(p, "#ck-int-plus"), "trace": last_trace(p, "int_plus_one")}
    r["screenshot"] = c.shot(p, "s4_wrong_type_cookie")
    ctx.close()
    r["status"] = "anomaly"
    return r


def s5_big_localstorage(c: Ctx, rec: Recorder) -> dict:
    """Very large LocalStorage value: 300k (under socket buffer) and 1.2M chars (over 1e6 bytes)."""
    r: dict = {}
    for n in (300_000, 1_200_000):
        ctx = c.context(rec)
        tag = f"s5_{n}"
        p = c.page(ctx, rec, tag)
        p.goto(c.base + "/")
        wait_hydrated(p)
        p.evaluate(f"localStorage.setItem('hyd_big', 'x'.repeat({n}))")
        t0 = time.time()
        p.reload()
        hyd = wait_hydrated(p, 20000)
        r[f"{n}_hydrated"] = hyd
        r[f"{n}_time_to_hydrated_s"] = round(time.time() - t0, 2) if hyd else None
        r[f"{n}_big_len"] = text(p, "#big-len")
        p.wait_for_timeout(1500)
        evs = [e for e in rec.ws_events if e["tag"] == tag]
        r[f"{n}_ws_opens"] = sum(1 for e in evs if e["ev"] == "open")
        r[f"{n}_ws_closes"] = sum(1 for e in evs if e["ev"] == "close")
        r[f"{n}_hyd_flag"] = text(p, "#hyd-flag")
        r[f"{n}_screenshot"] = c.shot(p, f"s5_big_{n}")
        r[f"{n}_frames_head"] = summarize_frames(rec.ws_frames, tag)[:12]
        ctx.close()
    r["status"] = "pass" if r["300000_hydrated"] and r["300000_big_len"] == "300000" else "fail"
    return r


def s6_on_load_variety(c: Ctx, rec: Recorder) -> dict:
    r: dict = {"checks": {}}
    ctx = c.context(rec)
    p = c.page(ctx, rec, "s6")
    # redirect on direct load
    p.goto(c.base + "/redir")
    ok = wait_until(p, lambda: p.url.endswith("/other") and text(p, "#page-other"), 15000)
    wait_hydrated(p)
    r["redir_direct"] = {"url": p.url, "other_count": text(p, "#other-count"), "trace": jtext(p, "#trace"), "hyd": text(p, "#hyd-flag")}
    r["checks"]["redir_direct"] = bool(ok) and r["redir_direct"]["hyd"] == "H:yes"
    # redirect via client nav
    p.click("#nav-home")
    wait_hydrated(p)
    p.click("#nav-redir")
    ok = wait_until(p, lambda: p.url.endswith("/other") and text(p, "#page-other"), 15000)
    wait_hydrated(p)
    p.wait_for_timeout(500)
    r["redir_client"] = {"url": p.url, "other_count": text(p, "#other-count"), "hyd": text(p, "#hyd-flag")}
    r["checks"]["redir_client"] = bool(ok) and r["redir_client"]["hyd"] == "H:yes"
    # background on_load
    p.goto(c.base + "/bgload")
    t0 = time.time()
    hyd = wait_hydrated(p)
    t_h = time.time() - t0
    done = wait_text(p, "#bg-status", "done", 10000)
    r["bgload"] = {"hydrated": hyd, "t_hydrated_s": round(t_h, 2), "done": done, "t_done_s": round(time.time() - t0, 2), "timeline": series(timeline(p), "bg-status")}
    r["checks"]["bgload"] = hyd and done
    # raising on_load
    p.goto(c.base + "/raise")
    hyd = wait_hydrated(p, 10000)
    p.wait_for_timeout(1000)
    before = text(p, "#counter")
    p.click("#inc")
    p.wait_for_timeout(800)
    r["raise"] = {"hydrated": hyd, "hyd_flag": text(p, "#hyd-flag"), "counter_before_after": [before, text(p, "#counter")], "screenshot": c.shot(p, "s6_raise")}
    r["checks"]["raise_page_usable"] = r["raise"]["counter_before_after"][0] != r["raise"]["counter_before_after"][1]
    # multi on_load ordering with root client storage
    p.goto(c.base + "/")
    wait_hydrated(p)
    p.evaluate(f"localStorage.setItem('{ROOT}.ls_plain_rx_state_', 'ls-from-browser')")
    p.goto(c.base + "/multi")
    wait_hydrated(p)
    p.wait_for_timeout(800)
    r["multi"] = {"order": jtext(p, "#multi-order"), "sub_saw": text(p, "#sub-saw")}
    mo = r["multi"]["order"] or []
    r["checks"]["multi_order"] = len(mo) >= 2 and mo[-2].startswith("A(ls=ls-from-browser") and mo[-1].startswith("B(root_ls=ls-from-browser")
    # call_script in on_load
    p.goto(c.base + "/script")
    wait_hydrated(p)
    ok = wait_until(p, lambda: text(p, "#script-result") not in (None, ""), 8000)
    r["script"] = text(p, "#script-result")
    r["checks"]["script"] = r["script"] == "42"
    # on_load on a state that owns LocalStorage
    p.evaluate("localStorage.setItem('hyd_lsl', 'lsl-from-browser')")
    p.goto(c.base + "/lsload")
    wait_hydrated(p)
    p.wait_for_timeout(500)
    r["lsload"] = {"val": text(p, "#lsl-val"), "saw": jtext(p, "#lsl-saw")}
    saw = r["lsload"]["saw"] or []
    r["checks"]["lsload_saw_browser_value"] = bool(saw) and saw[-1] == "saw=lsl-from-browser"
    # client-nav to /lsload as well
    p.click("#nav-home")
    wait_hydrated(p)
    p.evaluate("localStorage.setItem('hyd_lsl', 'lsl-changed-before-nav')")
    p.click("#nav-lsload")
    wait_hydrated(p)
    p.wait_for_timeout(500)
    saw = jtext(p, "#lsl-saw") or []
    r["lsload_client_nav_saw"] = saw[-1] if saw else None
    r["checks"]["lsload_client_nav"] = r["lsload_client_nav_saw"] == "saw=lsl-changed-before-nav"
    ctx.close()
    r["status"] = "pass" if all(r["checks"].values()) else "fail"
    return r


def s6b_slow_supersede(c: Ctx, rec: Recorder) -> dict:
    """Slow on_load (4 steps, 2s apart): navigate away mid-way via link and via back."""
    r: dict = {}
    # (a) direct load /slow then client link to /other at ~2.5s
    ctx = c.context(rec)
    p = c.page(ctx, rec, "s6b")
    p.goto(c.base + "/slow")
    wait_hydrated(p, 15000) if False else None
    wait_text(p, "#slow-progress", "2", 8000)
    p.wait_for_timeout(300)
    at_nav = text(p, "#slow-progress")
    p.click("#nav-other")
    wait_until(p, lambda: text(p, "#page-other"), 5000)
    p.wait_for_timeout(7000)
    tr = jtext(p, "#trace") or []
    r["link"] = {"progress_at_nav": at_nav, "progress_after_7s": text(p, "#slow-progress-other"), "trace": [t for t in tr if "slow" in t or "other" in t], "hyd": text(p, "#hyd-flag")}
    # (b) client nav into /slow from /other, then browser back at ~2.5s
    p.click("#clear-trace")
    p.wait_for_timeout(300)
    p.click("#nav-slow")
    wait_text(p, "#slow-progress", "2", 8000)
    p.wait_for_timeout(300)
    at_back = text(p, "#slow-progress")
    p.go_back()
    wait_until(p, lambda: text(p, "#page-other"), 5000)
    p.wait_for_timeout(7000)
    tr = jtext(p, "#trace") or []
    r["back"] = {"progress_at_back": at_back, "progress_after_7s": text(p, "#slow-progress-other"), "trace": [t for t in tr if "slow" in t or "other" in t], "hyd": text(p, "#hyd-flag")}
    # (c) forward again: slow runs again fully
    p.go_forward()
    ok = wait_text(p, "#slow-progress", "4", 12000)
    r["forward_completes"] = ok
    ctx.close()
    ok_link = r["link"]["progress_after_7s"] == r["link"]["progress_at_nav"] and not any("step4" in t for t in r["link"]["trace"])
    ok_back = r["back"]["progress_after_7s"] == r["back"]["progress_at_back"] and not any("step4" in t for t in r["back"]["trace"])
    r["checks"] = {"link_cancels": ok_link, "back_cancels": ok_back, "forward_completes": ok}
    r["status"] = "pass" if all(r["checks"].values()) else "fail"
    return r


def s7_gate_once(c: Ctx, rec: Recorder) -> dict:
    """rx.cond(is_hydrated) gate: spinner -> content, flag flips to yes exactly once per load."""
    r: dict = {}
    ctx = c.context(rec)
    p = c.page(ctx, rec, "s7")
    p.goto(c.base + "/gate")
    wait_hydrated(p)
    p.wait_for_timeout(1500)
    tl = timeline(p)
    flag = series(tl, "hyd-flag")
    r["direct"] = {"hyd_flag_series": flag, "content_series": series(tl, "gate-content"), "spinner_series": series(tl, "gate-spinner"), "gate_loads": text(p, "#gate-loads")}
    yes_flips = sum(1 for (_, v) in flag if v == "H:yes")
    r["direct_yes_flips"] = yes_flips
    # client nav away and back (let home's own on_load chain finish first)
    p.click("#nav-home")
    wait_until(p, lambda: text(p, "#page-index"), 5000)
    p.wait_for_timeout(2000)
    wait_hydrated(p)
    p.evaluate("window.__hyd.log = []")
    p.click("#nav-gate")
    wait_until(p, lambda: text(p, "#page-gate"), 5000)
    wait_hydrated(p)
    p.wait_for_timeout(1500)
    tl = timeline(p)
    flag = series(tl, "hyd-flag")
    r["client_nav"] = {"hyd_flag_series": flag, "content_series": series(tl, "gate-content")}
    r["client_yes_flips"] = sum(1 for (_, v) in flag if v == "H:yes")
    cs = r["client_nav"]["content_series"]
    first_no = next((t for (t, v) in flag if v == "H:no"), None)
    shown_before = [t for (t, v) in cs if v == "CONTENT" and first_no is not None and t <= first_no]
    r["client_nav_gated_content_flash_ms"] = (first_no - shown_before[0]) if shown_before else 0
    # reload
    p.reload()
    wait_hydrated(p)
    p.wait_for_timeout(1500)
    tl = timeline(p)
    r["reload"] = {"hyd_flag_series": series(tl, "hyd-flag")}
    r["reload_yes_flips"] = sum(1 for (_, v) in series(tl, "hyd-flag") if v == "H:yes")
    ctx.close()
    ok = r["direct_yes_flips"] == 1 and r["client_yes_flips"] == 1 and r["reload_yes_flips"] == 1
    r["status"] = "pass" if ok else "fail"
    return r


def s8_defaults(c: Ctx, rec: Recorder) -> dict:
    """Per-session/env/import-mutated/typed defaults: displayed == backend values, frames inspected."""
    r: dict = {"contexts": []}
    for i in range(2):
        ctx = c.context(rec)
        tag = f"s8_{i}"
        p = c.page(ctx, rec, tag)
        p.goto(c.base + "/defaults")
        wait_hydrated(p)
        p.wait_for_timeout(500)
        shown = {k: text(p, "#" + k) for k in ["d-session-id", "d-created", "d-fixed-dt", "d-env", "d-items", "d-mapping", "d-point", "d-flt", "d-pid", "d-summary"]}
        p.click("#d-report")
        p.wait_for_timeout(800)
        rep = last_trace(p, "backend_defaults=")
        backend = json.loads(rep.split("=", 1)[1]) if rep else {}
        tl = timeline(p)
        first_paint = {k: (series(tl, k)[0][1] if series(tl, k) else None) for k in ["d-session-id", "d-items", "d-pid", "d-env", "d-summary"]}
        mism = {}
        if backend:
            if shown["d-session-id"] != backend["session_id"]:
                mism["session_id"] = [shown["d-session-id"], backend["session_id"]]
            if json.loads(shown["d-items"]) != backend["items"]:
                mism["items"] = [shown["d-items"], backend["items"]]
            if shown["d-pid"] != backend["pid_default"]:
                mism["pid_default"] = [shown["d-pid"], backend["pid_default"]]
            if shown["d-summary"] != backend["summary"]:
                mism["summary"] = [shown["d-summary"], backend["summary"]]
            if shown["d-env"] != backend["env_val"]:
                mism["env_val"] = [shown["d-env"], backend["env_val"]]
        r["contexts"].append({"shown": shown, "backend": backend, "first_paint": first_paint, "mismatch": mism, "frames": summarize_frames(rec.ws_frames, tag)[:6], "timeline_session": series(tl, "d-session-id")})
        if i == 0:
            c.shot(p, "s8_defaults")
        ctx.close()
    ids = [x["shown"]["d-session-id"] for x in r["contexts"]]
    r["distinct_session_ids"] = len(set(ids)) == 2
    bad = [x["mismatch"] for x in r["contexts"] if x["mismatch"]]
    r["status"] = "pass" if (not bad and r["distinct_session_ids"]) else "fail"
    return r


def s9_dynamic_routes(c: Ctx, rec: Recorder) -> dict:
    r: dict = {}
    ctx = c.context(rec)
    p = c.page(ctx, rec, "s9")
    p.goto(c.base + "/items/1")
    wait_hydrated(p)
    p.wait_for_timeout(300)
    r["direct_1"] = {"trace": jtext(p, "#item-trace"), "params": text(p, "#item-params")}
    p.click("#nav-item2")
    wait_until(p, lambda: "id=2" in (text(p, "#item-trace") or ""), 5000)
    wait_hydrated(p)
    r["nav_2"] = {"url": p.url, "trace": jtext(p, "#item-trace"), "params": text(p, "#item-params")}
    p.go_back()
    wait_until(p, lambda: p.url.endswith("/items/1"), 5000)
    wait_hydrated(p)
    p.wait_for_timeout(800)
    r["back_1"] = {"url": p.url, "trace": jtext(p, "#item-trace"), "params": text(p, "#item-params")}
    p.go_forward()
    wait_until(p, lambda: p.url.endswith("/items/2"), 5000)
    wait_hydrated(p)
    p.wait_for_timeout(800)
    r["fwd_2"] = {"url": p.url, "trace": jtext(p, "#item-trace"), "params": text(p, "#item-params")}
    # catch-all
    p.goto(c.base + "/docs/a/b")
    wait_hydrated(p)
    p.wait_for_timeout(300)
    r["docs_direct"] = jtext(p, "#docs-trace")
    p.click("#nav-docsroot")
    wait_hydrated(p)
    p.wait_for_timeout(500)
    r["docs_root_nav"] = jtext(p, "#docs-trace")
    p.goto(c.base + "/docs")
    wait_hydrated(p)
    p.wait_for_timeout(300)
    r["docs_root_direct"] = jtext(p, "#docs-trace")
    ctx.close()
    tr = r["fwd_2"]["trace"] or []
    ok = (
        any("id=1|path=/items/1" in t for t in (r["direct_1"]["trace"] or []))
        and (r["nav_2"]["trace"] or [""])[-1].startswith("id=2|path=/items/2")
        and (r["back_1"]["trace"] or [""])[-1].startswith("id=1|path=/items/1")
        and tr and tr[-1].startswith("id=2|path=/items/2")
        and (r["docs_direct"] or [""])[-1].startswith("splat=['a', 'b']|path=/docs/a/b")
    )
    r["status"] = "pass" if ok else "fail"
    return r


def s10_click_before_hydrate(c: Ctx, rec: Recorder) -> dict:
    """Click the always-visible button as soon as it exists (before hydration)."""
    r: dict = {"runs": []}
    for i in range(3):
        ctx = c.context(rec)
        tag = f"s10_{i}"
        p = c.page(ctx, rec, tag)
        p.goto(c.base + "/clickfast", wait_until="commit")
        p.wait_for_selector("#cf-always", timeout=15000)
        flag_at_click = text(p, "#hyd-flag", 1000)
        p.click("#cf-always", timeout=5000)
        wait_hydrated(p)
        wait_until(p, lambda: "load" in (text(p, "#cf-log") or ""), 8000)
        p.wait_for_timeout(1500)
        log = jtext(p, "#cf-log")
        p.click("#cf-gated")
        p.wait_for_timeout(800)
        log2 = jtext(p, "#cf-log")
        r["runs"].append({"flag_at_click": flag_at_click, "log": log, "log_after_gated": log2})
        ctx.close()
    r["status"] = "anomaly"
    return r


def s11_upload_nav(c: Ctx, rec: Recorder, upload_file: str) -> dict:
    """#7357: while client X's buffered upload is in flight, client Y's slow on_load is superseded by navigation."""
    r: dict = {}
    cx = c.context(rec)
    x = c.page(cx, rec, "s11x")
    x.goto(c.base + "/upload")
    wait_hydrated(x)
    x.set_input_files("#up1 input[type=file]", upload_file)
    x.click("#do-upload")
    started = wait_text(x, "#up-status", "started 1", 5000)
    r["upload_started"] = started
    cy = c.context(rec)
    y = c.page(cy, rec, "s11y")
    y.goto(c.base + "/slow")
    wait_text(y, "#slow-progress", "2", 8000)
    y.wait_for_timeout(300)
    at_nav = text(y, "#slow-progress")
    y.click("#nav-other")
    wait_until(y, lambda: text(y, "#page-other"), 5000)
    y.wait_for_timeout(6500)
    tr = jtext(y, "#trace") or []
    r["y"] = {"progress_at_nav": at_nav, "progress_after": text(y, "#slow-progress-other"), "trace": [t for t in tr if "slow" in t or "other" in t]}
    r["upload_done"] = wait_text(x, "#up-status", "done 1", 10000)
    # same client: start upload, then navigate within the same tab
    x.click("#nav-slow")
    wait_text(x, "#slow-progress", "1", 8000)
    r["same_client_note"] = "upload handler holds the token's lock (non-background), so same-client nav waits for it"
    cx.close()
    cy.close()
    ok = r["y"]["progress_after"] == r["y"]["progress_at_nav"] and not any("step4" in t for t in r["y"]["trace"])
    r["status"] = "pass" if ok else "fail"
    return r


def s12_nested_fail(c: Ctx, rec: Recorder) -> dict:
    r: dict = {}
    ctx = c.context(rec)
    p = c.page(ctx, rec, "s12")
    p.goto(c.base + "/nested")
    wait_hydrated(p)
    p.click("#nested-btn")
    p.wait_for_timeout(800)
    r["after_list"] = jtext(p, "#nested-log")
    p.click("#fail-then-ok")
    p.wait_for_timeout(1500)
    r["after_fail_then_ok"] = jtext(p, "#nested-log")
    ctx.close()
    ok = r["after_list"] == ["a", "b", "c"] and r["after_fail_then_ok"] == ["a", "b", "c", "c"]
    r["status"] = "pass" if ok else "fail"
    return r


def s13_timing(c: Ctx, rec: Recorder, n: int = int(__import__("os").environ.get("S13_N", "6"))) -> dict:
    """Time from navigation start to first delta frame and to hydrated flag, fresh contexts."""
    r: dict = {"runs": []}
    for i in range(n):
        ctx = c.context(rec)
        tag = f"s13_{i}"
        p = c.page(ctx, rec, tag)
        p.goto(c.base + "/other")
        wait_hydrated(p)
        p.wait_for_timeout(300)
        origin = p.evaluate("performance.timeOrigin")
        nav = p.evaluate("JSON.parse(JSON.stringify(performance.getEntriesByType('navigation')[0]))")
        frames = [f for f in rec.ws_frames if f["tag"] == tag]
        first_out = next((f for f in frames if f["dir"] == "out" and str(f["p"]).startswith(("40", "42"))), None)
        first_delta = next((f for f in frames if f["dir"] == "in" and str(f["p"]).startswith("42") and '"delta"' in str(f["p"])), None)
        flag = series(timeline(p), "hyd-flag")
        t_yes = next((t for (t, v) in flag if v == "H:yes"), None)
        n_in_before_yes = None
        r["runs"].append({
            "dcl_ms": round(nav.get("domContentLoadedEventEnd", 0)),
            "load_ms": round(nav.get("loadEventEnd", 0)),
            "first_out_ms": round(first_out["wall"] - origin) if first_out else None,
            "first_delta_ms": round(first_delta["wall"] - origin) if first_delta else None,
            "hydrated_ms": t_yes,
            "frames_out": sum(1 for f in frames if f["dir"] == "out" and str(f["p"]).startswith(("40", "42"))),
            "frames_in": sum(1 for f in frames if f["dir"] == "in" and str(f["p"]).startswith(("40", "42"))),
            "bytes_in": sum(f["len"] for f in frames if f["dir"] == "in"),
            "bytes_out": sum(f["len"] for f in frames if f["dir"] == "out"),
            "n_in_before_yes": n_in_before_yes,
        })
        ctx.close()

    def med(key):
        vals = sorted(x[key] for x in r["runs"][1:] if x[key] is not None)
        return vals[len(vals) // 2] if vals else None

    r["median_excl_first"] = {k: med(k) for k in ["dcl_ms", "first_out_ms", "first_delta_ms", "hydrated_ms", "frames_out", "frames_in", "bytes_in", "bytes_out"]}
    r["status"] = "pass"
    return r


SCENARIOS = {
    "s1": s1_storage_roundtrip,
    "s1b": s1b_defaults_written,
    "s2": s2_sync_two_tabs,
    "s3": s3_clear_storage,
    "s4": s4_wrong_type_cookie,
    "s5": s5_big_localstorage,
    "s6": s6_on_load_variety,
    "s6b": s6b_slow_supersede,
    "s7": s7_gate_once,
    "s8": s8_defaults,
    "s9": s9_dynamic_routes,
    "s10": s10_click_before_hydrate,
    "s11": s11_upload_nav,
    "s12": s12_nested_fail,
    "s13": s13_timing,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    upload_file = out / "upload.txt"
    upload_file.write_text("hello upload\n" * 100)
    names = [n for n in args.only.split(",") if n] or list(SCENARIOS)
    summary = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=CHROMIUM)
        c = Ctx(browser, args.base, out, args.label)
        for name in names:
            rec = Recorder()
            t0 = time.time()
            try:
                fn = SCENARIOS[name]
                res = fn(c, rec, str(upload_file)) if name == "s11" else fn(c, rec)
            except Exception as ex:  # noqa: BLE001
                res = {"status": "error", "error": f"{type(ex).__name__}: {ex}", "tb": traceback.format_exc()}
            res["duration_s"] = round(time.time() - t0, 1)
            res["anomalies"] = rec.anomalies()
            save_json(out / f"{name}.json", res)
            save_json(out / f"{name}.raw.json", rec.dump())
            an = res["anomalies"]
            summary[name] = {"status": res["status"], "console_err_warn": len(an["console_err_warn"]), "pageerrors": len(an["pageerrors"]), "failed": len(an["failed"]), "http_errors": len(an["http_errors"])}
            print(f"[{args.label}] {name}: {res['status']} ({res['duration_s']}s) {summary[name]}", flush=True)
        browser.close()
    save_json(out / "summary.json", summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
