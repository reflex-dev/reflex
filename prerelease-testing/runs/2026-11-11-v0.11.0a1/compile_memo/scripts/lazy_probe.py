"""Load a page, list JS requests with sizes; on /dyn click recharts and dump the box. Usage: lazy_probe.py base"""
import sys, time, json
from playwright.sync_api import sync_playwright
base = sys.argv[1].rstrip("/")
out = {}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for path in ["/", "/", "/plotly", "/recharts", "/dyn"]:
        pg = b.new_page()
        sizes = {}
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
        pg.on("console", lambda m: errs.append(m.text[:200]) if m.type in ("error", "warning") and "404" not in m.text else None)
        def onresp(r):
            u = r.url
            if u.endswith(".js"):
                try:
                    sizes[u.split("/")[-1]] = len(r.body())
                except Exception:
                    sizes[u.split("/")[-1]] = -1
        pg.on("response", onresp)
        pg.goto(base + path); time.sleep(3)
        rec = {"n_js": len(sizes), "js_bytes": sum(v for v in sizes.values() if v > 0),
               "libs": sorted(k for k in sizes if any(s in k.lower() for s in ("recharts", "plotly", "glide", "lucide", "banana", "info", "es6", "dataeditor", "radix")))}
        if path == "/dyn":
            pg.click("#dyn-b-recharts"); time.sleep(3)
            rec["dyn_recharts_html"] = pg.inner_html("#dyn-box")[:300]
        rec["errors"] = errs
        out[path + ("#2" if path in out else "")] = rec
        pg.close()
    b.close()
print(json.dumps(out, indent=1))
