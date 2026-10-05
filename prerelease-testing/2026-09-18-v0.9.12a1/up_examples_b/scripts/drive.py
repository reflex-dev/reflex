"""Generic Playwright driver: runs a JSON action list, captures console/network anomalies."""
import json, re, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

BENIGN = [
    re.compile(r"Hey developer.*HydrateFallback|reactrouter\.com/start/framework/route-module"),
    re.compile(r"\[vite\] (connecting|connected)"),
    re.compile(r"Download the React DevTools"),
]
def benign(t): return any(p.search(t) for p in BENIGN)

def main():
    url = sys.argv[1]
    actions = json.loads(Path(sys.argv[2]).read_text())
    outdir = Path(sys.argv[3]); outdir.mkdir(parents=True, exist_ok=True)
    console, errors, failed, bad = [], [], [], []
    results = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        ctx = b.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        page.on("console", lambda m: console.append(f"[{m.type}] {m.text}") if not benign(m.text) else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("requestfailed", lambda r: failed.append(f"{r.method} {r.url} :: {r.failure}"))
        page.on("response", lambda r: bad.append(f"{r.status} {r.request.method} {r.url}") if r.status >= 400 else None)
        page.goto(url, wait_until="load", timeout=60000)
        page.wait_for_timeout(1500)
        for i, act in enumerate(actions):
            k, v = next(iter(act.items()))
            try:
                if k == "click": page.click(v, timeout=15000)
                elif k == "fill": page.fill(v[0], v[1], timeout=15000)
                elif k == "press": page.press(v[0], v[1], timeout=15000)
                elif k == "kbd": page.keyboard.press(v)
                elif k == "type": page.keyboard.type(v, delay=60)
                elif k == "goto": page.goto(v, wait_until="load", timeout=60000)
                elif k == "wait": page.wait_for_timeout(v)
                elif k == "expect_text": page.wait_for_selector(f"text={v}", timeout=15000)
                elif k == "expect_missing":
                    assert page.query_selector(f"text={v}") is None, f"present: {v}"
                elif k == "screenshot": page.screenshot(path=str(outdir / v), full_page=True)
                elif k == "dump":
                    (outdir / v).write_text(page.inner_text("body"))
                elif k == "html":
                    (outdir / v).write_text(page.content())
                elif k == "eval": results.append(("eval", page.evaluate(v)))
                elif k == "reload": page.reload(wait_until="load", timeout=60000)
                else: raise ValueError(f"unknown action {k}")
                results.append((i, k, "ok"))
            except Exception as e:
                results.append((i, k, f"FAIL {type(e).__name__}: {e}"))
                try: page.screenshot(path=str(outdir / f"fail_{i}.png"), full_page=True)
                except Exception: pass
        page.wait_for_timeout(800)
        ctx.close(); b.close()
    rep = {"url": url, "actions": [list(map(str, r)) for r in results],
           "console": console, "page_errors": errors, "failed_requests": failed, "http_errors": bad}
    (outdir / "report.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1)[:6000])
    ok = all(str(r[-1]) == "ok" for r in results if len(r) == 3) and not errors and not console
    sys.exit(0 if ok else 1)

main()
