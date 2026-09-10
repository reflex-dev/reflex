"""Playwright checks for route matching (memoized per (path, frontend_path) in 0.9.11a1).

Usage: NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python pw_routes.py \
   --url http://localhost:3181 --out logs/pw_routes_smoke --label smoke [--frontend-path /app]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pwlib import Capture, dump, launch, text_of, wait_text  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

RESULTS: list[dict] = []


def rec(name, status, details, **extra):
    RESULTS.append({"name": name, "status": status, "details": details, **extra})
    print(f"[{status.upper():7}] {name}: {details}", flush=True)


def parse_last(t: str) -> dict:
    body = t.split("=", 1)[1]
    if not body:
        return {}
    parts = body.split("|")
    d = {"n": int(parts[0])}
    for p in parts[1:]:
        k, _, v = p.partition("=")
        d[k] = v
    if "params" in d:
        v = json.loads(d["params"])
        if isinstance(v, str):  # router.page.params is a proxy object: json.dumps(default=str) yields its repr
            import ast
            v = ast.literal_eval(v)
        d["params"] = v
    return d


# (link id or None, direct path, expected route pattern, expected raw prefix, expected params subset)
CASES = [
    ("l-item1", "/item/1", "/item/[id]", "/item/1", {"id": "1"}),
    ("l-item2", "/item/2", "/item/[id]", "/item/2", {"id": "2"}),
    ("l-item2q", "/item/2?q=x&z=9#frag", "/item/[id]", "/item/2?q=x&z=9#frag", {"id": "2", "q": "x", "z": "9"}),
    ("l-docs", "/docs", "/docs/[[...splat]]", "/docs", {}),
    ("l-docsab", "/docs/a/b", "/docs/[[...splat]]", "/docs/a/b", {"splat": ["a", "b"]}),
    ("l-postsall", "/posts/all/7", "/posts/all/[x]", "/posts/all/7", {"x": "7"}),
    ("l-postsallbare", "/posts/all", "/posts/[id]", "/posts/all", {"id": "all"}),
    ("l-posts42", "/posts/42", "/posts/[id]", "/posts/42", {"id": "42"}),
    ("l-s0", "/static-0", "/static-0", "/static-0", {}),
    ("l-s149", "/static-149", "/static-149", "/static-149", {}),
    ("l-apple", "/apple", "/apple", "/apple", {}),
    ("l-app", "/app", "/app", "/app", {}),
    ("l-item1", "/item/1", "/item/[id]", "/item/1", {"id": "1"}),  # revisit: cache hit
    ("l-home", "/", "/", "/", {}),
]
# direct-load only: url-encoded / unicode dynamic segments, deep splat with trailing slash, many distinct ids (cache growth)
DIRECT_ONLY = [
    ("/item/a%20b", "/item/[id]", "/item/a", {}),
    ("/item/h%C3%A9llo", "/item/[id]", "/item/h", {}),
    ("/docs/x/y/z/", "/docs/[[...splat]]", "/docs/x/y/z", {"splat": ["x", "y", "z"]}),
] + [(f"/item/{i}", "/item/[id]", f"/item/{i}", {"id": str(i)}) for i in range(100, 110)]


def expect(page, case, n_expected, mode, fp):
    link, path, route, raw, params = case
    try:
        last = wait_text(page, "#last", lambda t: parse_last(t).get("n") == n_expected, 10)
        d = parse_last(last)
    except Exception as e:  # noqa: BLE001
        rec(f"routes.{mode}.{path}", "fail", f"expected n={n_expected}: {type(e).__name__}: {e}")
        return {}
    got_path = d.get("path")
    path_ok = got_path == route or (route == "/" and got_path == "/index")
    got_raw = (d.get("raw") or "")
    raw_ok = got_raw.removeprefix(fp).startswith(raw) if fp else got_raw.startswith(raw)
    params_ok = all(d.get("params", {}).get(k) == v for k, v in params.items())
    ok = d.get("n") == n_expected and path_ok and raw_ok and params_ok
    rec(f"routes.{mode}.{path}", "pass" if ok else "fail",
        f"expected n={n_expected} path={route} raw~{fp}{raw} params⊇{params}; got {last}" + ("" if path_ok else f"  <-- WRONG ROUTE MATCH: {got_path}"))
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", default="")
    ap.add_argument("--frontend-path", default="")
    a = ap.parse_args()
    Path(a.out).mkdir(parents=True, exist_ok=True)
    fp = a.frontend_path
    base = a.url.rstrip("/") + fp
    ws_sent: list[dict] = []
    with sync_playwright() as pw:
        browser = launch(pw)
        ctx = browser.new_context(); page = ctx.new_page(); cap = Capture(page, a.label)

        def on_ws(ws):
            def on_sent(payload):
                # socket.io event frames look like 42/_event,["event",{...}]; record the router_data the client sent
                if isinstance(payload, str) and '"pathname"' in payload:
                    try:
                        body = json.loads(payload[payload.index("["):])
                        ev = body[1]
                        ws_sent.append({"name": ev.get("name", "")[-40:], "pathname": ev.get("router_data", {}).get("pathname"),
                                        "asPath": ev.get("router_data", {}).get("asPath")})
                    except Exception:  # noqa: BLE001
                        ws_sent.append({"raw": payload[:200]})
            ws.on("framesent", on_sent)
        page.on("websocket", on_ws)
        n = 0
        try:
            page.goto(base + "/")
            page.wait_for_selector("#last")
            last = wait_text(page, "#last", lambda t: parse_last(t).get("n") == 1, 20)
            d = parse_last(last); n = 1
            rec("routes.initial_load_index", "pass" if (d.get("path") in ("/", "/index") and d.get("n") == 1) else "fail", last)
            # client-side navigation via links
            for case in CASES:
                n += 1
                try:
                    page.click(f"#{case[0]}")
                except Exception as e:  # noqa: BLE001
                    rec(f"routes.client_nav.{case[1]}.click", "fail", f"{type(e).__name__}: {e}"); continue
                expect(page, case, n, "client_nav", fp)
            page.screenshot(path=f"{a.out}/after_client_nav.png")
            # direct loads (full page load) of the same paths; the state token persists in sessionStorage
            for case in CASES:
                n += 1
                try:
                    page.goto(base + case[1]); page.wait_for_selector("#last", timeout=15000)
                except Exception as e:  # noqa: BLE001
                    rec(f"routes.direct_load.{case[1]}.goto", "fail", f"{type(e).__name__}: {e}"); continue
                expect(page, case, n, "direct_load", fp)
            for case in DIRECT_ONLY:
                n += 1
                try:
                    page.goto(base + case[0]); page.wait_for_selector("#last", timeout=15000)
                except Exception as e:  # noqa: BLE001
                    rec(f"routes.direct_only.{case[0]}.goto", "fail", f"{type(e).__name__}: {e}"); continue
                expect(page, (None, *case), n, "direct_only", fp)
            # trailing slash + index alias direct loads
            for path, route in (("/item/5/", "/item/[id]"), ("/static-7/", "/static-7"), ("/index", "/")):
                n += 1
                try:
                    page.goto(base + path); page.wait_for_selector("#last", timeout=10000)
                    last = wait_text(page, "#last", lambda t: parse_last(t).get("n") == n, 10)
                    d = parse_last(last)
                    ok = d.get("path") == route or (route == "/" and d.get("path") == "/index")
                    rec(f"routes.direct_load.{path}", "pass" if ok else "anomaly" if d.get("n") == n else "fail", f"expected path={route}; got {last}")
                except Exception as e:  # noqa: BLE001
                    body = page.locator("body").inner_text()[:200].replace("\n", " ")
                    # the frontend shows the 404 page; check whether the backend still ran an on_load for this URL
                    page.goto(base + "/"); page.wait_for_selector("#last")
                    n += 1
                    last = wait_text(page, "#last", lambda t: parse_last(t).get("n") == n, 10)
                    prev = ""
                    try:
                        vis = text_of(page, "#visits").split(" ;; ")
                        prev = next((v for v in vis if v.startswith(f"{n-1}|")), "")
                    except Exception:  # noqa: BLE001
                        pass
                    if prev:
                        rec(f"routes.direct_load.{path}", "anomaly", f"frontend rendered 404 (body={body!r}) but the backend fired an on_load for it: {prev}")
                    else:
                        n -= 1
                        rec(f"routes.direct_load.{path}", "anomaly", f"frontend rendered 404 (body={body!r}); no backend on_load recorded either")
            page.goto(base + "/"); page.wait_for_selector("#last"); n += 1
            wait_text(page, "#last", lambda t: parse_last(t).get("n") == n, 10)
            total = text_of(page, "#n_loads")
            rec("routes.total_on_load_count", "pass" if total == f"n_loads={n}" else "fail", f"expected n_loads={n}, got {total}")
            page.screenshot(path=f"{a.out}/final.png")
        except Exception as e:  # noqa: BLE001
            rec("routes.EXC", "fail", f"{type(e).__name__}: {e}")
        finally:
            an = cap.anomalies()
            RESULTS.append({"name": "browser_capture", "status": "info", "details": json.dumps(an)})
            print("CAPTURE:", json.dumps(an, indent=1))
            pn = sorted({(w.get("pathname"), w.get("asPath")) for w in ws_sent if "pathname" in w}, key=str)
            RESULTS.append({"name": "ws_router_data_sent", "status": "info", "details": f"distinct (pathname, asPath) the client sent: {pn}"})
            print("WS pathnames sent:", pn)
            dump(f"{a.out}/results.json", RESULTS)
            dump(f"{a.out}/console.json", cap.console)
            dump(f"{a.out}/ws_sent.json", ws_sent)
            try:
                dump(f"{a.out}/visits.txt", text_of(page, "#visits"))
            except Exception:  # noqa: BLE001
                pass
            browser.close()
    fails = [r for r in RESULTS if r["status"] == "fail"]
    print(f"SUMMARY {a.label}: {len(RESULTS)} entries, {len(fails)} fail")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
