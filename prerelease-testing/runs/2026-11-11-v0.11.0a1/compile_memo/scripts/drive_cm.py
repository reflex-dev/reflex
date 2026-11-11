"""Drive the `cm` app through every page; print JSON results.

Usage: NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python drive_cm.py http://localhost:3300 <out.json> [pages,comma,sep]
"""

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
OUT = Path(sys.argv[2])
PAGES = sys.argv[3].split(",") if len(sys.argv) > 3 else None
SHOTS = OUT.parent / (OUT.stem + "_shots")
SHOTS.mkdir(parents=True, exist_ok=True)
BENIGN = ("Hey developer", "[vite] connect", "Download the React DevTools", "HydrateFallback")

res: dict = {"base": BASE}
cur = {"page": "init"}
console: list = []
reqs: list = []


def txt(page, sel, timeout=8000):
    try:
        return page.locator(sel).first.inner_text(timeout=timeout)
    except Exception as e:  # noqa: BLE001
        return f"<ERR {type(e).__name__}>"


def wait_text(page, sel, needle, timeout=8000):
    t0 = time.time()
    while time.time() - t0 < timeout / 1000:
        t = txt(page, sel, 1000)
        if needle in t:
            return True
        time.sleep(0.15)
    return False


def renders(page):
    return page.evaluate("() => ({...(window.__renders || {})})")


def goto(page, path, marker):
    cur["page"] = path
    page.goto(BASE + path)
    ok = page.locator(marker).first.wait_for(timeout=30000) or True
    # wait for websocket hydrate: n text not empty / a state value visible
    time.sleep(1.2)
    return ok


def run_home(page, r):
    goto(page, "/", "#page-home")
    wait_text(page, "#branch", "page", 10000)
    r["initial_branch"] = txt(page, "#branch")
    r0 = renders(page)
    for _ in range(3):
        page.click("#inc")
    r["n_after_3"] = wait_text(page, "#n", "n=3")
    time.sleep(0.5)
    r1 = renders(page)
    for _ in range(2):
        page.click("#bump-other")
    wait_text(page, "#other", "other=2")
    time.sleep(0.5)
    r2 = renders(page)
    r["renders"] = {"initial": r0, "after_inc3": r1, "after_other2": r2}
    for b in page.locator(".memo-go").all():
        b.click()
    wait_text(page, "#clicks", "a,b,c")
    r["clicks"] = txt(page, "#clicks")
    page.click("#toggle")
    wait_text(page, "#br-b", "branch B")
    time.sleep(0.4)
    page.click("#toggle")
    wait_text(page, "#br-a", "branch A")
    time.sleep(0.8)
    r["branch_after_2_toggles"] = txt(page, "#branch")
    page.click("#cs1")
    page.click("#cs1")
    time.sleep(0.6)
    r["cstate"] = [txt(page, "#cs1"), txt(page, "#cs2")]
    if page.locator("#shared-inc").count():
        page.click("#shared-inc")
        page.locator(".cs-inc").first.click()
        page.locator(".cs-inc").first.click()
        time.sleep(0.4)
        r["client_state"] = {"shared": txt(page, "#shared-val"), "memo": [t.inner_text() for t in page.locator(".cs-val").all()]}
    page.click("#focus-f")
    time.sleep(0.5)
    r["fstring_focus_active"] = page.evaluate("() => document.activeElement && (document.activeElement.id || document.activeElement.className)")
    r["fstring_input_dom_id"] = page.evaluate("() => document.querySelector('.fin input, input.fin, .fin')?.id ?? null")
    page.screenshot(path=str(SHOTS / "home.png"), full_page=True)


def loop_snapshot(page):
    return {
        "mounted": txt(page, "#mounted"),
        "unmounted": txt(page, "#unmounted"),
        "hooklog": page.evaluate("() => (window.__hooklog || []).join(',')"),
        "items": [t.inner_text() for t in page.locator(".loop-item").all()],
    }


def run_loop(page, r, path="/loop", marker="#page-loop"):
    goto(page, "/", "#page-home")
    page.click("#clear-log")
    time.sleep(0.6)
    page.evaluate("() => { window.__hooklog = [] }")
    page.click(f"#nav-{path.strip('/')}")
    page.locator(marker).wait_for(timeout=15000)
    time.sleep(1.5)
    r["initial"] = loop_snapshot(page)
    steps = ["#add", "#rm-first", "#reverse"] + (["#rm-mid"] if path == "/loop" else [])
    for s in steps:
        page.evaluate("() => { window.__hooklog = [] }")
        page.click(s)
        time.sleep(1.0)
        r[f"after_{s[1:]}"] = loop_snapshot(page)
        page.click("#clear-log")
        time.sleep(0.5)
    if path == "/loop":
        # focus second row's input through f-string id ref
        btns = page.locator(".row-focus").all()
        if len(btns) >= 2:
            btns[0].click()
            time.sleep(0.4)
            inputs = page.locator(".row-input").all()
            r["row_focus_first_btn_focuses_index"] = page.evaluate(
                "() => { const a = document.activeElement; const ins = [...document.querySelectorAll('.row-input input, input.row-input')]; return ins.indexOf(a); }"
            )
            r["row_input_ids"] = page.evaluate("() => [...document.querySelectorAll('.row-input input, input.row-input')].map(e => e.id)")
    page.screenshot(path=str(SHOTS / f"{path.strip('/')}.png"), full_page=True)


def run_refs(page, r):
    goto(page, "/refs", "#page-refs")
    r["raw_prop"] = txt(page, "#raw-prop", 3000)
    r["refs_hook"] = page.evaluate("() => window.__refs_hook ?? null")
    page.click("#b-focus")
    time.sleep(0.3)
    r["set_focus_active"] = page.evaluate("() => document.activeElement?.id")
    page.click("#b-setvalue")
    time.sleep(0.4)
    r["set_value"] = page.evaluate("() => document.getElementById('plain_input')?.value")
    page.click("#b-scroll")
    time.sleep(1.0)
    r["scroll_y"] = page.evaluate("() => window.scrollY")
    page.evaluate("() => window.scrollTo(0,0)")
    page.click("#b-callscript")
    time.sleep(0.6)
    r["call_script_value"] = page.evaluate("() => document.getElementById('other_input')?.value")
    r["log_after_call_script"] = txt(page, "#focus-log")
    page.click("#b-rawvar")
    time.sleep(0.4)
    r["raw_var_value"] = page.evaluate("() => document.getElementById('plain_input')?.value")
    page.click("#b-callfn")
    time.sleep(0.6)
    r["log_after_callfn"] = txt(page, "#focus-log")
    page.click("#form-submit")
    time.sleep(0.6)
    r["log_after_form"] = txt(page, "#focus-log")
    page.screenshot(path=str(SHOTS / "refs.png"))


def set_files(page, names):
    files = [{"name": n, "mimeType": "text/plain", "buffer": (n * 3).encode()} for n in names]
    page.locator("#up1 input[type=file]").set_input_files(files)
    time.sleep(0.4)


def run_upload(page, r):
    goto(page, "/upload", "#page-upload")
    set_files(page, ["a.txt", "b.txt"])
    r["selected"] = txt(page, "#selected")
    page.click("#b-up-direct")
    wait_text(page, "#uploaded", "b.txt")
    r["direct"] = txt(page, "#uploaded")
    r["progress"] = txt(page, "#progress")
    page.click("#b-reset")
    time.sleep(0.5)
    # backend toast with progress
    set_files(page, ["t1.txt"])
    page.click("#b-up-toast")
    try:
        page.get_by_text("Upload now").click(timeout=8000)
        wait_text(page, "#uploaded", "t1.txt")
    except Exception as e:  # noqa: BLE001
        r["toast_err"] = str(e)[:200]
    r["backend_toast"] = txt(page, "#uploaded")
    r["backend_toast_progress"] = txt(page, "#progress")
    page.click("#b-reset")
    time.sleep(0.4)
    # selection changed after toast shown
    set_files(page, ["old.txt"])
    page.click("#b-up-ftoast")
    time.sleep(0.5)
    set_files(page, ["new1.txt", "new2.txt"])
    try:
        page.get_by_text("FUpload").click(timeout=8000)
        wait_text(page, "#uploaded", "new")
    except Exception as e:  # noqa: BLE001
        r["ftoast_err"] = str(e)[:200]
    time.sleep(0.5)
    r["frontend_toast_changed_selection"] = txt(page, "#uploaded")
    page.click("#b-reset")
    time.sleep(0.4)
    set_files(page, ["cs.txt"])
    page.click("#b-up-cs")
    wait_text(page, "#uploaded", "cs.txt")
    r["frontend_call_script"] = txt(page, "#uploaded")
    page.click("#b-reset")
    time.sleep(0.4)
    set_files(page, ["bcs.txt"])
    page.click("#b-up-bcs")
    wait_text(page, "#uploaded", "bcs.txt")
    r["backend_call_script"] = txt(page, "#uploaded")
    page.click("#b-clear")
    time.sleep(0.4)
    r["selected_after_clear"] = txt(page, "#selected")
    page.screenshot(path=str(SHOTS / "upload.png"))


def run_lib(page, r, path, marker, probe):
    before = len(reqs)
    goto(page, path, marker)
    time.sleep(2.5)
    r["probe_count"] = page.locator(probe).count()
    r["js_requests"] = sorted({u.split("/")[-1].split("?")[0] for u in reqs[before:] if ".js" in u or ".mjs" in u})
    page.screenshot(path=str(SHOTS / f"{path.strip('/')}.png"))


def run_dyn(page, r):
    goto(page, "/dyn", "#page-dyn")
    r["initial"] = txt(page, "#dyn-box")
    for w, probe in [("icon", "#dyn-box svg"), ("recharts", "#dyn-box .recharts-wrapper"), ("callout", "#dyn-box svg")]:
        before = len(reqs)
        page.click(f"#dyn-b-{w}")
        try:
            page.locator(probe).first.wait_for(timeout=10000)
            r[w] = "ok"
        except Exception:  # noqa: BLE001
            r[w] = "MISSING " + txt(page, "#dyn-box", 1000)[:100]
        r[w + "_reqs"] = sorted({u.split("/")[-1].split("?")[0][:60] for u in reqs[before:]})
    r["window_reflex_keys"] = page.evaluate("() => Object.keys(window.__reflex || {}).sort()")
    page.screenshot(path=str(SHOTS / "dyn.png"))


def svg_info(page, sel):
    return page.evaluate(
        "(sel) => { const e = document.querySelector(sel); if (!e) return 'NO-ELEMENT'; const s = e.querySelector('svg') || (e.tagName==='svg'?e:null); return s ? (s.getAttribute('class')||'svg') + ' paths=' + s.querySelectorAll('path,rect,circle,line,polyline').length : 'NO-SVG'; }",
        sel,
    )


def run_comps(page, r):
    goto(page, "/comps", "#page-comps")
    time.sleep(1.0)
    for co in ["co-str", "co-comp", "co-cond", "co-match", "co-var", "co-memo"]:
        r[co] = svg_info(page, f"#{co}")
    page.click("#toggle")
    time.sleep(0.5)
    r["co-cond_after_toggle"] = svg_info(page, "#co-cond")
    page.click("#cycle-co")
    time.sleep(0.5)
    r["co-match_after_cycle"] = svg_info(page, "#co-match")
    page.click("#cycle-co")
    time.sleep(0.5)
    r["co-match_after_cycle2"] = svg_info(page, "#co-match")
    r["code_text"] = txt(page, "#cb-text")[:60]
    r["code_var"] = txt(page, "#cb-var")[:60]
    r["icon_rows"] = page.evaluate(
        "() => [...document.querySelectorAll('.icn-row')].map(row => row.innerText.trim() + ' => ' + ((row.querySelector('svg')||{}).getAttribute ? (row.querySelector('svg').getAttribute('class')||'') + ' paths=' + row.querySelector('svg').querySelectorAll('path,rect,circle,line,polyline').length : 'NO-SVG'))"
    )
    r["icn-static"] = page.evaluate("() => { const s = document.querySelector('#icn-static'); return s ? (s.getAttribute('class')||'') + ' paths=' + s.querySelectorAll('path,rect,circle,line,polyline').length : 'NO'; }")
    seq = []
    for _ in range(7):
        seq.append(txt(page, "#icn-name") + " -> " + page.evaluate("() => { const s = document.querySelector('#icn-var'); return s ? (s.getAttribute('class')||'') + ' paths=' + s.querySelectorAll('path,rect,circle,line,polyline').length : 'NO'; }"))
        page.click("#next-icon")
        time.sleep(0.5)
    r["icn-var-seq"] = seq
    page.screenshot(path=str(SHOTS / "comps.png"), full_page=True)


def run_rowfocus(page, r):
    goto(page, "/rowfocus", "#page-rowfocus")
    js = "() => { const a = document.activeElement; const ins = [...document.querySelectorAll('.rf-input input, input.rf-input')]; return ins.indexOf(a); }"
    out = []
    for i, b in enumerate(page.locator(".rf-focus").all()):
        b.click()
        time.sleep(0.3)
        out.append(page.evaluate(js))
    r["focus_btn_i_focuses"] = out
    for b in page.locator(".rf-value").all():
        b.click()
        time.sleep(0.3)
    r["values_after_set_value_each"] = page.evaluate("() => [...document.querySelectorAll('.rf-input input, input.rf-input')].map(e => e.value)")
    r["ids"] = page.evaluate("() => [...document.querySelectorAll('.rf-input input, input.rf-input')].map(e => e.id)")


SUITE = {
    "rowfocus": run_rowfocus,
    "home": run_home,
    "loop": lambda p, r: run_loop(p, r),
    "loopmemo": lambda p, r: run_loop(p, r, "/loopmemo", "#page-loopmemo"),
    "refs": run_refs,
    "upload": run_upload,
    "plotly": lambda p, r: run_lib(p, r, "/plotly", "#page-plotly", ".js-plotly-plot"),
    "recharts": lambda p, r: run_lib(p, r, "/recharts", "#page-recharts", ".recharts-wrapper"),
    "editor": lambda p, r: run_lib(p, r, "/editor", "#page-editor", "canvas"),
    "dyn": run_dyn,
    "comps": run_comps,
}

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    page = ctx.new_page()
    page.on("console", lambda m: console.append({"page": cur["page"], "type": m.type, "text": m.text[:400]}) if m.type in ("error", "warning") and not any(x in m.text for x in BENIGN) else None)
    page.on("pageerror", lambda e: console.append({"page": cur["page"], "type": "pageerror", "text": str(e)[:400]}))
    page.on("request", lambda q: reqs.append(q.url))
    page.on("requestfailed", lambda q: console.append({"page": cur["page"], "type": "reqfailed", "text": q.url[:200] + " " + str(q.failure)}))
    page.on("response", lambda s: console.append({"page": cur["page"], "type": f"http{s.status}", "text": s.url[:200]}) if s.status >= 400 and "favicon" not in s.url else None)
    for name, fn in SUITE.items():
        if PAGES and name not in PAGES:
            continue
        r: dict = {}
        t0 = time.time()
        try:
            fn(page, r)
        except Exception as e:  # noqa: BLE001
            r["EXC"] = f"{type(e).__name__}: {str(e)[:300]}"
            try:
                page.screenshot(path=str(SHOTS / f"{name}_exc.png"))
            except Exception:  # noqa: BLE001
                pass
        r["secs"] = round(time.time() - t0, 1)
        res[name] = r
    res["console"] = console
    b.close()

OUT.write_text(json.dumps(res, indent=1))
print(json.dumps(res, indent=1)[:200000])
