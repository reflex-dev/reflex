"""Drive core_a2 in Chromium.

Usage: NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python drive_core.py <base_url> <outdir> <label> [pages]
  pages: comma list of home,cs,storage,dunder (default all), or schema1 / schema2 (token file in <outdir>/<label>-token.txt)
Writes <outdir>/<label>.json and screenshots. Captures console (all types), failed requests, >=400 responses, ws frame counts.
"""

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

base, outdir, label = sys.argv[1].rstrip("/"), Path(sys.argv[2]), sys.argv[3]
pages = (sys.argv[4] if len(sys.argv) > 4 else "home,cs,storage,dunder").split(",")
outdir.mkdir(parents=True, exist_ok=True)
res, console, bad, ws_frames = {}, [], [], {"sent": 0, "recv": 0}
token_file = outdir / f"{label.rsplit('-', 1)[0]}-token.txt"


def attach(page, tag):
    page.on("console", lambda m: console.append(f"[{tag}] {m.type}: {m.text[:400]}"))
    page.on("pageerror", lambda e: console.append(f"[{tag}] PAGEERROR: {str(e)[:400]}"))
    page.on("requestfailed", lambda r: bad.append(f"[{tag}] FAILED {r.url} {r.failure}"))
    page.on("response", lambda r: bad.append(f"[{tag}] {r.status} {r.url}") if r.status >= 400 else None)

    def on_ws(ws):
        ws.on("framesent", lambda f: ws_frames.__setitem__("sent", ws_frames["sent"] + 1))
        ws.on("framereceived", lambda f: ws_frames.__setitem__("recv", ws_frames["recv"] + 1))

    page.on("websocket", on_ws)


def txt(page, sel):
    try:
        return page.inner_text(sel, timeout=5000)
    except Exception as e:  # noqa: BLE001
        return f"<missing: {type(e).__name__}>"


def wait_text(page, sel, expected, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        if txt(page, sel) == expected:
            return True
        time.sleep(0.2)
    return False


def goto(page, path):
    page.goto(base + path, wait_until="networkidle", timeout=180000)
    page.wait_for_function("() => !!window.sessionStorage.getItem('token')", timeout=60000)
    time.sleep(1.0)


def storage_dump(page):
    return page.evaluate("""() => { const o = {}; for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i); o[k] = localStorage.getItem(k); } return {local: o, cookie: document.cookie}; }""")


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = browser.new_context()
    page = ctx.new_page()
    attach(page, "tab1")

    if "home" in pages:
        goto(page, "/")
        page.wait_for_selector("#shown", state="attached", timeout=60000)
        r = res.setdefault("home", {})
        r["fstring_label"] = txt(page, "#fstring_label")
        r["sized_width"] = page.evaluate("() => getComputedStyle(document.querySelector('#sized')).width")
        r["items"] = page.eval_on_selector_all(".item", "els => els.map(e => e.innerText)")
        r["classvar_label"] = txt(page, "#classvar_label")
        r["cs_btn_label"] = txt(page, "#cs_btn")
        page.click("#cs_btn")
        wait_text(page, "#cs_count", "5")
        r["cs_count_after_click"] = txt(page, "#cs_count")

        def step(name, btn, wait=1.5):
            page.click(btn)
            time.sleep(wait)
            r[name] = {"shown": txt(page, "#shown"), "log": txt(page, "#log")}

        step("1_show", "#show")
        time.sleep(3.5)
        step("2_show_after_3.5s", "#show")
        step("3_set_instance", "#set_instance")
        step("4_show", "#show")
        step("5_reset", "#reset")
        step("6_show", "#show")
        page.reload(wait_until="networkidle")
        page.wait_for_selector("#shown", state="attached")
        time.sleep(2)
        r["7_after_reload"] = {"shown": txt(page, "#shown"), "log": txt(page, "#log")}
        page.screenshot(path=str(outdir / f"{label}-home.png"), full_page=True)

    if "cs" in pages:
        goto(page, "/cs")
        r = res.setdefault("cs", {})
        page.wait_for_selector("#count_a", timeout=60000)

        def snap(name):
            r[name] = {k: txt(page, f"#{k}") for k in ["count_a", "label_a", "tags_a", "hidden_a", "count_b", "label_b", "tags_b", "hidden_b"]}

        snap("0_initial")
        page.click("#incr_a")
        page.click("#incr_a")
        wait_text(page, "#count_a", "12")
        page.click("#incr_b")
        wait_text(page, "#count_b", "21")
        snap("1_after_incr_a2_b1")
        page.click("#reset_a")
        wait_text(page, "#count_a", "10")
        snap("2_after_reset_a")
        page.click("#showhidden_a")
        page.click("#showhidden_b")
        time.sleep(1.5)
        snap("3_after_showhidden")
        page.click("#reconf_b")
        time.sleep(1.5)
        snap("4_after_reconf_b(type(self).count=77;reset)")
        et = {}
        for box in ["et_default", "et_editme", "et_fun"]:
            et[box] = txt(page, f"#{box}")
        page.click("#et_editme p, #et_editme span")
        time.sleep(1.0)
        inp = page.locator("#et_editme input")
        et["editme_input_visible"] = inp.count() > 0
        if inp.count():
            et["editme_input_value"] = inp.input_value()
            inp.fill("Edited!")
            inp.press("Enter")
            time.sleep(1.5)
        et["after_edit"] = {b: txt(page, f"#{b}") for b in ["et_default", "et_editme", "et_fun"]}
        r["editable_text"] = et
        page.screenshot(path=str(outdir / f"{label}-cs.png"), full_page=True)
        page.reload(wait_until="networkidle")
        time.sleep(2)
        snap("5_after_reload_same_session")
        page2 = ctx.new_page()
        attach(page2, "tab2")
        goto(page2, "/cs")
        page2.wait_for_selector("#count_a", timeout=60000)
        time.sleep(1)
        r["6_new_session_tab2"] = {k: txt(page2, f"#{k}") for k in ["count_a", "label_a", "tags_a", "count_b", "label_b", "tags_b"]}
        page2.close()

    if "storage" in pages:
        goto(page, "/storage")
        r = res.setdefault("storage", {})
        ids = ["v_ls_fac_assigned", "v_ls_declared_fac", "v_ls_plain", "v_ls_untouched", "v_ck", "lscs_value"]
        page.wait_for_selector("#v_ls_plain", timeout=60000)
        time.sleep(1)
        r["0_initial"] = {k: txt(page, f"#{k}") for k in ids}
        r["0_browser_storage"] = storage_dump(page)
        page.click("#change_all")
        page.click("#lscs_change")
        time.sleep(2)
        r["1_after_change"] = {k: txt(page, f"#{k}") for k in ids}
        r["1_browser_storage"] = storage_dump(page)
        page2 = ctx.new_page()  # new tab: new token, same localStorage/cookies
        attach(page2, "tab2")
        goto(page2, "/storage")
        page2.wait_for_selector("#v_ls_plain", timeout=60000)
        time.sleep(1.5)
        r["2_new_tab_same_browser"] = {k: txt(page2, f"#{k}") for k in ids}
        page2.close()
        page.click("#st_reset")
        time.sleep(2)
        r["3_after_reset"] = {k: txt(page, f"#{k}") for k in ids}
        r["3_browser_storage"] = storage_dump(page)
        page.screenshot(path=str(outdir / f"{label}-storage.png"), full_page=True)

    if "dunder" in pages:
        goto(page, "/dunder")
        r = res.setdefault("dunder", {})
        ids = ["d_view", "d_counter_cv", "d_fielded_cv"]
        page.wait_for_selector("#d_view", state="attached", timeout=60000)

        def dsnap(name, btn=None, wait=1.5):
            if btn:
                page.click(btn)
                time.sleep(wait)
            r[name] = {k: txt(page, f"#{k}") for k in ids}

        dsnap("0_initial")
        dsnap("1_bump", "#d_bump")
        dsnap("2_bump_silent", "#d_bump_silent")
        dsnap("3_bump_silent", "#d_bump_silent")
        dsnap("4_show", "#d_show")
        dsnap("5_bump_fielded", "#d_bump_fielded")
        dsnap("6_bump_mx", "#d_bump_mx")
        dsnap("7_bump_mx", "#d_bump_mx")
        page.reload(wait_until="networkidle")
        time.sleep(2)
        dsnap("8_after_reload")
        dsnap("9_show_after_reload", "#d_show")
        page.screenshot(path=str(outdir / f"{label}-dunder.png"), full_page=True)

    if "schema1" in pages:
        goto(page, "/schema")
        page.wait_for_selector("#sch_count", timeout=60000)
        r = res.setdefault("schema1", {})
        r["0_initial"] = {"count": txt(page, "#sch_count"), "note": txt(page, "#sch_note")}
        page.click("#sch_set42")
        wait_text(page, "#sch_count", "42")
        time.sleep(4)  # > disk debounce
        r["1_after_set42"] = {"count": txt(page, "#sch_count"), "note": txt(page, "#sch_note")}
        tok = page.evaluate("() => sessionStorage.getItem('token')")
        token_file.write_text(tok)
        r["token"] = tok

    if "schema2" in pages:
        tok = token_file.read_text().strip()
        ctx2 = browser.new_context()
        ctx2.add_init_script(f"window.sessionStorage.setItem('token', {json.dumps(tok)});")
        pg = ctx2.new_page()
        attach(pg, "resumed")
        goto(pg, "/schema")
        pg.wait_for_selector("#sch_count", timeout=60000)
        time.sleep(2)
        r = res.setdefault("schema2", {})
        r["resumed_token"] = tok
        r["token_in_page"] = pg.evaluate("() => sessionStorage.getItem('token')")
        r["after_restart"] = {"count": txt(pg, "#sch_count"), "note": txt(pg, "#sch_note")}
        pg.screenshot(path=str(outdir / f"{label}-schema2.png"), full_page=True)

    browser.close()

res["console"] = console
res["bad_responses"] = bad
res["ws_frames"] = ws_frames
(outdir / f"{label}.json").write_text(json.dumps(res, indent=1))
print(json.dumps(res, indent=1))
