"""Focused verification probe: per-route row counts, toasts, console errors, failed requests."""
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
OUT = Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
ROUTES = sys.argv[3].split(",")
report = {}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context(viewport={"width": 1500, "height": 1000})
    for route in ROUTES:
        page = ctx.new_page()
        msgs, failed, bad = [], [], []
        page.on("console", lambda m: msgs.append(f"{m.type}: {m.text[:250]}"))
        page.on("pageerror", lambda e: msgs.append(f"pageerror: {str(e)[:250]}"))
        page.on("requestfailed", lambda r: failed.append(f"{r.url[:220]} :: {r.failure}"))
        page.on("response", lambda r: bad.append(f"{r.status} {r.url[:220]}") if r.status >= 400 else None)
        r = {}
        try:
            page.goto(BASE + route, wait_until="load", timeout=60000)
            page.wait_for_timeout(9000)
            r["rows"] = page.locator(".ag-center-cols-container .ag-row").count()
            r["toasts"] = [t.inner_text()[:200] for t in page.locator("[data-sonner-toast]").all()]
            r["body_head"] = page.inner_text("body")[:200].replace("\n", " | ")
        except Exception as e:
            r["error"] = str(e)[:300]
        r["console"] = [m for m in msgs if "HydrateFallback" not in m and "[vite]" not in m and "React DevTools" not in m][:12]
        r["failed_requests"] = failed[:8]
        r["bad_responses"] = bad[:8]
        try:
            page.screenshot(path=str(OUT / ((route.strip("/").replace("/", "_") or "index") + ".png")), full_page=False)
        except Exception as _e:
            r["screenshot_error"] = str(_e)[:120]
        page.close()
        report[route] = r
        print(route, json.dumps(r)[:400])
    ctx.close(); b.close()
(OUT / "verify_report.json").write_text(json.dumps(report, indent=2))
