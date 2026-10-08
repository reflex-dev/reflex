"""Drive apps/c4e2e (a4_class_state). Usage:
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python drive_c4e2e.py <base> <out.json>"""
import json
import os
import sys
import tempfile
import time

from playwright.sync_api import sync_playwright

assert "/envs/driver/" in sys.executable, sys.executable
base, out = sys.argv[1].rstrip("/"), sys.argv[2]
S_IDS = ["sync", "ck", "ann", "ss", "opt", "plainstr"]
res, console, bad, checks = {}, [], [], []


def check(name, got, want):
    ok = got == want
    checks.append(("PASS" if ok else "FAIL", name, got, want))


def txt(p, i):
    return p.inner_text(f"#{i}", timeout=8000)


def wait_txt(p, i, want, t=8.0):
    end = time.time() + t
    while time.time() < end:
        try:
            if txt(p, i) == want:
                return want
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.2)
    return txt(p, i)


def store(p, ctx):
    d = p.evaluate("() => ({local: Object.fromEntries(Object.entries(localStorage).filter(([k]) => !k.startsWith('debug') && k !== 'chakra-ui-color-mode')), session: Object.fromEntries(Object.entries(sessionStorage))})")
    d["cookies"] = [{k: c[k] for k in ("name", "value", "path", "sameSite", "expires")} for c in ctx.cookies() if c["name"].startswith("k_")]
    for c in d["cookies"]:
        c["expires_in_s"] = round(c.pop("expires") - time.time()) if c["expires"] > 0 else "session"
    return d


def hyd(p):
    p.wait_for_function("() => document.querySelector('#hyd')?.textContent === 'H:yes'", timeout=90000)
    time.sleep(1.2)


def open_page(ctx, tag, path="/"):
    p = ctx.new_page()
    p.on("console", lambda m: console.append(f"[{tag}] {m.type}: {m.text[:300]}"))
    p.on("pageerror", lambda e: console.append(f"[{tag}] PAGEERROR: {str(e)[:300]}"))
    p.on("response", lambda r: bad.append(f"[{tag}] {r.status} {r.url}") if r.status >= 400 else None)
    p.goto(base + path, wait_until="networkidle", timeout=240000)
    hyd(p)
    return p


with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    # ---- index: storage ----
    p1 = open_page(ctx, "tab1")
    res["outcomes"] = txt(p1, "outcomes")
    res["0_initial"] = {k: txt(p1, f"v_{k}") for k in S_IDS}
    res["0_store"] = store(p1, ctx)
    check("index initial values", res["0_initial"], {k: ("assigned" if k != "opt" else "") for k in S_IDS})
    p1.click("#change_a")
    time.sleep(2)
    res["1_store"] = store(p1, ctx)
    loc, ses = res["1_store"]["local"], res["1_store"]["session"]
    check("k_sync written", loc.get("k_sync"), "A-sync")
    check("ann under default key (not k_ann)", (any(v == "A-ann" for k, v in loc.items() if k != "k_ann"), "k_ann" in loc), (True, False))
    check("k_ss in session", ses.get("k_ss"), "A-ss")
    check("opt NOT stored (ordinary var)", "k_opt" in loc, False)
    check("plainstr NOT stored (ordinary var)", "k_plainstr" in loc, False)
    ck = [c for c in res["1_store"]["cookies"] if c["name"] == "k_ck_opt"]
    check("cookie k_ck_opt Strict ~3600s", (ck[0]["value"], ck[0]["sameSite"], 3500 < ck[0]["expires_in_s"] <= 3600) if ck else None, ("A-ck", "Strict", True))
    p2 = open_page(ctx, "tab2")
    res["2_new_tab"] = {k: txt(p2, f"v_{k}") for k in S_IDS}
    check("new tab restores storage vars", {k: res["2_new_tab"][k] for k in ("sync", "ck", "ann")}, {"sync": "A-sync", "ck": "A-ck", "ann": "A-ann"})
    check("new tab: ordinary vars back to defaults", (res["2_new_tab"]["opt"], res["2_new_tab"]["plainstr"]), ("", "assigned"))
    p2.click("#set_sync")
    check("sync=True propagates to tab1", wait_txt(p1, "v_sync", "from-tab2"), "from-tab2")
    p2.close()
    # ---- /cs ----
    p1.goto(base + "/cs", wait_until="networkidle")
    hyd(p1)
    res["cs"] = {i: txt(p1, i) for i in ("et1_text", "et2_text", "et3_text", "tt_a", "tt_b", "pick_x", "picks_x", "pick_y", "picks_y")}
    check("EditableText initial_value per component", (res["cs"]["et1_text"], res["cs"]["et2_text"], res["cs"]["et3_text"]), ("Click edit to change this text.", "Second", "Third"))
    check("ThemeToggle per-key initial", (res["cs"]["tt_a"], res["cs"]["tt_b"]), ("dark", "light"))
    check("ThemePick initial + per-component factory", (res["cs"]["pick_x"], res["cs"]["picks_x"], res["cs"]["pick_y"], res["cs"]["picks_y"]), ("cx", "init-x", "cy", "init-y"))
    p1.click("#choose_x")
    time.sleep(1.5)
    res["cs_store"] = store(p1, ctx)["local"]
    check("pick_x stored under its own key", (res["cs_store"].get("pick_x"), "pick_y" in res["cs_store"]), ("dark-x", False))
    p1.click("#et2_edit")
    time.sleep(0.8)
    p1.fill("input", "Edited2")
    p1.keyboard.press("Enter")
    time.sleep(1.2)
    res["cs_after_edit"] = {i: txt(p1, i) for i in ("et1_text", "et2_text", "et3_text")}
    check("EditableText edit one instance", res["cs_after_edit"], {"et1_text": "Click edit to change this text.", "et2_text": "Edited2", "et3_text": "Third"})
    p1.reload(wait_until="networkidle")
    hyd(p1)
    res["cs_reload"] = {i: txt(p1, i) for i in ("pick_x", "picks_x", "pick_y")}
    check("after reload pick_x from storage, pick_y default", (res["cs_reload"]["pick_x"], res["cs_reload"]["pick_y"]), ("dark-x", "cy"))
    # ---- /post/[slug] (client-side nav from index, then direct load) ----
    p1.goto(base + "/", wait_until="networkidle")
    hyd(p1)
    p1.click("#to_post")
    res["post_nav"] = (wait_txt(p1, "slug", "hello-world"), wait_txt(p1, "views", "1"))
    check("dynamic route via client nav", res["post_nav"], ("hello-world", "1"))
    p1.goto(base + "/post/second", wait_until="networkidle")
    hyd(p1)
    res["post_direct"] = (txt(p1, "slug"), txt(p1, "views"))
    check("dynamic route direct load", res["post_direct"][0], "second")
    # ---- /misc ----
    p1.goto(base + "/misc", wait_until="networkidle")
    hyd(p1)
    g = lambda: {i: txt(p1, i) for i in ("limit", "items", "total", "log", "mval", "collab", "cfg", "cnt")}  # noqa: E731
    res["misc0"] = g()
    check("misc initial", res["misc0"], {"limit": "10", "items": "cfg", "total": "21", "log": "", "mval": "3", "collab": "2", "cfg": "CFG=7 childlimit=6", "cnt": "3"})
    p1.click("#bump")
    check("bump", (wait_txt(p1, "limit", "11"), txt(p1, "items"), wait_txt(p1, "total", "24")), ("11", "cfg,b", "24"))
    p1.click("#reset")
    check("reset -> configured defaults", (wait_txt(p1, "limit", "10"), txt(p1, "items"), wait_txt(p1, "total", "21")), ("10", "cfg", "21"))
    p1.click("#bg")
    check("background task", (wait_txt(p1, "limit", "110"), wait_txt(p1, "log", "bg CFG=7")), ("110", "bg CFG=7"))
    p1.click("#other")
    check("get_state other", wait_txt(p1, "log", "bg CFG=7|other.mval=3"), "bg CFG=7|other.mval=3")
    p1.click("#mbump")
    check("mixin handler", wait_txt(p1, "mval", "4"), "4")
    p1.click("#link")
    check("SharedState link", wait_txt(p1, "collab", "3"), "3")
    p1.click("#inc")
    check("SharedState inc", wait_txt(p1, "collab", "4"), "4")
    p1.click("#cntp")
    check("client_state", wait_txt(p1, "cnt", "4"), "4")
    fn = os.path.join(tempfile.mkdtemp(), "x.txt")
    open(fn, "w").write("hello-upload")
    p1.set_input_files("#up input[type=file]", fn)
    p1.click("#do_up")
    check("upload handler", "upload x.txt 12" in wait_txt(p1, "log", "bg CFG=7|other.mval=3|upload x.txt 12"), True)
    res["misc_end"] = g()
    p1.screenshot(path=out.replace(".json", ".png"), full_page=True)
    b.close()
res["checks"] = checks
res["console"] = [c for c in console if "Hey developer" not in c and "[vite]" not in c and "DevTools" not in c and "Disconnect websocket" not in c]
res["bad"] = bad
open(out, "w").write(json.dumps(res, indent=1, default=str))
for c in checks:
    print(*c)
print("console:", json.dumps(res["console"], indent=1))
print("bad:", bad)
print(f"SUMMARY {sum(c[0] == 'PASS' for c in checks)}/{len(checks)} pass")
