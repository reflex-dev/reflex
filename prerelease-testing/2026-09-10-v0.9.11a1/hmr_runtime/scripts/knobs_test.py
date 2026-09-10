"""Check a running dev server started with/without REFLEX_DEV_PROD_REACT / REFLEX_VITE_WARMUP_ROUTES (#7021).

Measures first-visit latency of not-yet-visited routes (client-side navigation and cold full loads),
inspects the served React prebundle for dev/prod markers, checks fibers for _debugOwner (dev-only),
verifies events + navigation work, and (with --edit) edits the app source and records whether Vite sends
`update` or `full-reload`, whether the page reloaded, and whether client state reset.

    NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python knobs_test.py \
        --url http://localhost:3100 --backend-port 8100 --mode prod_react --out $SB/apps/hmr_runtime/logs/knobs_prod_react \
        --app-file .../hmr_app.py --edit
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

CHROMIUM = "/opt/pw-browsers/chromium"
BENIGN = [
    re.compile(r"Hey developer.*HydrateFallback|reactrouter\.com/start/framework/route-module"),
    re.compile(r"\[vite\] (connecting|connected)"),
    re.compile(r"Download the React DevTools"),
]
ROUTES = [("/page2", "#page2-heading"), ("/page3", "#page3-heading"), ("/about", "#about-heading"), ("/long", "#long-end")]
DEV_MARKERS = ["react.development.js", "react-dom-client.development.js", "Each child in a list should have a unique", "jsxDEV", "react-jsx-dev-runtime.development"]
PROD_MARKERS = ["react.production.js", "react-dom-client.production.js", "react-jsx-runtime.production"]


def marker_scan(text: str) -> dict:
    return {"dev": {m: text.count(m) for m in DEV_MARKERS if m in text}, "prod": {m: text.count(m) for m in PROD_MARKERS if m in text}, "bytes": len(text)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--backend-port", type=int, required=True)
    ap.add_argument("--mode", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--app-file")
    ap.add_argument("--edit", action="store_true")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report: dict = {"mode": args.mode, "url": args.url}
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        ctx = browser.new_context(viewport={"width": 1200, "height": 900})
        page = ctx.new_page()
        console, errors, failed, bad, vite_frames, loads = [], [], [], [], [], []
        page.on("console", lambda m: console.append((time.time(), m.type, m.text)))
        page.on("pageerror", lambda e: errors.append((time.time(), str(e))))
        page.on("requestfailed", lambda r: failed.append(f"{r.url} {r.failure}"))
        page.on("response", lambda r: r.status >= 400 and bad.append(f"{r.status} {r.url}"))
        page.on("load", lambda: loads.append(time.time()))
        react_module_urls = []

        def on_request(r):
            if "/node_modules/.vite/deps/" in r.url and re.search(r"/(react|react-dom|react-dom_client|react_jsx-runtime|react_jsx-dev-runtime|scheduler)[^/]*\.js", r.url):
                react_module_urls.append(r.url)

        page.on("request", on_request)

        def on_ws(ws):
            if f":{args.backend_port}/" in ws.url:
                return
            ws.on("framereceived", lambda payload: vite_frames.append((time.time(), payload)))

        page.on("websocket", on_ws)

        # Cold load of index.
        t0 = time.time()
        page.goto(args.url + "/", wait_until="networkidle")
        page.wait_for_selector("#memo-count", timeout=90000)
        report["index_cold_ms"] = round((time.time() - t0) * 1000)
        page.click("#inc-btn")
        page.wait_for_timeout(600)
        page.click("#inc-btn")
        page.wait_for_timeout(600)
        report["count_after_2_clicks"] = page.inner_text("#memo-count").strip()
        page.click("#cs-btn")
        page.wait_for_timeout(300)
        report["cs_after_click"] = page.inner_text("#cs-text").strip()
        page.click("#toggle-btn")
        page.wait_for_timeout(600)
        report["toggle_after_click"] = page.inner_text("#toggle-btn").strip()
        fiber = page.evaluate(
            """(() => { const el = document.getElementById('heading'); const k = Object.keys(el).find(k => k.startsWith('__reactFiber')); const f = el[k];
                return { fiberKey: !!k, has_debugOwner: f ? ('_debugOwner' in f) : null, has_debugInfo: f ? ('_debugInfo' in f) : null, has_debugStack: f ? ('_debugStack' in f) : null }; })()"""
        )
        report["fiber_debug_fields"] = fiber
        print("fiber debug fields:", fiber)

        # First-visit latency via client-side navigation.
        nav = {}
        for route, sel in ROUTES:
            t0 = time.time()
            page.click(f"#nav-{route.strip('/')}")
            page.wait_for_selector(sel, timeout=60000)
            nav[route] = round((time.time() - t0) * 1000)
        report["first_visit_client_nav_ms"] = nav
        print("first-visit client nav ms:", nav)
        # Second visit (already transformed) for reference.
        page.click("#nav-home")
        page.wait_for_selector("#heading", timeout=60000)
        nav2 = {}
        for route, sel in ROUTES:
            t0 = time.time()
            page.click(f"#nav-{route.strip('/')}")
            page.wait_for_selector(sel, timeout=60000)
            nav2[route] = round((time.time() - t0) * 1000)
        report["second_visit_client_nav_ms"] = nav2
        print("second-visit client nav ms:", nav2)
        page.click("#nav-home")
        page.wait_for_selector("#heading", timeout=60000)

        # Served React prebundle inspection.
        urls = sorted(set(react_module_urls))
        report["react_module_urls"] = urls
        scans = {}
        rc = ctx.request
        for u in urls:
            try:
                body = rc.get(u).text()
                scans[u.split("/deps/")[-1]] = marker_scan(body)
            except Exception as e:  # noqa: BLE001
                scans[u] = {"error": str(e)}
        # also fetch canonical dep names directly
        for name in ["react.js", "react-dom_client.js", "react_jsx-dev-runtime.js", "react_jsx-runtime.js", "react-dom.js"]:
            u = f"{args.url}/node_modules/.vite/deps/{name}"
            try:
                r = rc.get(u)
                scans[f"direct:{name}"] = {"status": r.status, **(marker_scan(r.text()) if r.status == 200 else {})}
            except Exception as e:  # noqa: BLE001
                scans[f"direct:{name}"] = {"error": str(e)}
        report["react_module_scan"] = scans
        for k, v in scans.items():
            print("  module", k, json.dumps(v))

        edit_result = None
        if args.edit and args.app_file:
            app_file = Path(args.app_file)
            src = app_file.read_text()
            old = 'rx.heading("HMR Runtime App", id="heading")'
            new = 'rx.heading("HMR Runtime App KNOB", id="heading")'
            assert old in src, "heading marker not found"
            cs_before = page.inner_text("#cs-text").strip()
            count_before = page.inner_text("#memo-count").strip()
            loads_before = len(loads)
            frames_before = len(vite_frames)
            t_edit = time.time()
            app_file.write_text(src.replace(old, new))
            deadline = time.time() + 60
            settled = False
            while time.time() < deadline:
                try:
                    if page.inner_text("#heading").strip() == "HMR Runtime App KNOB":
                        settled = True
                        break
                except Exception:  # noqa: BLE001
                    pass
                time.sleep(0.2)
            time.sleep(1.5)
            page.wait_for_selector("#cs-text", timeout=30000)
            frames = []
            for ts, payload in vite_frames[frames_before:]:
                try:
                    d = json.loads(payload)
                except Exception:  # noqa: BLE001
                    continue
                if d.get("type") in ("ping", "pong"):
                    continue
                frames.append(d.get("type") if d.get("type") != "update" else f"update:{[u.get('path') for u in d.get('updates', [])]}")
            edit_result = {
                "settled": settled,
                "edit_to_settle_s": round(time.time() - t_edit, 2),
                "vite_frames": frames,
                "page_loads_after_edit": len(loads) - loads_before,
                "cs_before": cs_before,
                "cs_after": page.inner_text("#cs-text").strip(),
                "count_before": count_before,
                "count_after": page.inner_text("#memo-count").strip(),
                "heading_after": page.inner_text("#heading").strip(),
            }
            print("edit result:", json.dumps(edit_result))
            # restore
            app_file.write_text(src)
            time.sleep(4)
        report["edit"] = edit_result
        page.screenshot(path=str(out / "final.png"))
        report["console_errors"] = [f"{k}: {t}" for ts, k, t in console if k in ("error", "warning") and not any(b.search(t) for b in BENIGN)]
        report["console_all"] = [f"{k}: {t[:200]}" for ts, k, t in console]
        report["page_errors"] = [e for ts, e in errors]
        report["failed_requests"] = failed
        report["bad_responses"] = bad
        print("console errors/warnings:", report["console_errors"])
        print("page errors:", report["page_errors"], "failed:", failed, "bad:", bad)
        ctx.close()

        # Cold full-page loads of each route in fresh contexts (includes SSR + module fetch); routes were
        # visited above so Vite has transformed them already -> this is "warm vite, cold browser".
        cold = {}
        for route, sel in ROUTES:
            c2 = browser.new_context()
            pg = c2.new_page()
            t0 = time.time()
            pg.goto(args.url + route, wait_until="commit")
            pg.wait_for_selector(sel, timeout=60000)
            cold[route] = round((time.time() - t0) * 1000)
            c2.close()
        report["full_load_fresh_context_ms"] = cold
        print("full load fresh context ms:", cold)
        browser.close()
    (out / "report.json").write_text(json.dumps(report, indent=2))
    print("report:", out / "report.json")


if __name__ == "__main__":
    main()
