"""Probe: does window.onerror get called (by otel export failure), and does it reach the backend?"""
import json, sys, time
from playwright.sync_api import sync_playwright

URL = sys.argv[1]
WAIT = int(sys.argv[2]) if len(sys.argv) > 2 else 30

console = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
    ctx = b.new_context()
    # Wrap window.onerror as soon as it is assigned, and log every call.
    ctx.add_init_script("""
      (() => {
        let real = undefined;
        Object.defineProperty(window, 'onerror', {
          configurable: true,
          get() { return real; },
          set(fn) {
            console.log('PROBE: window.onerror assigned, type=' + typeof fn);
            real = typeof fn === 'function' ? function (...a) {
              console.log('PROBE: window.onerror CALLED: ' + a[0]);
              return fn.apply(this, a);
            } : fn;
          }
        });
      })();
    """)
    page = ctx.new_page()
    page.on("console", lambda m: console.append(f"{m.type}: {m.text}"))
    page.goto(URL, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3000)
    page.click("#btn-inc")
    page.wait_for_timeout(1000)
    print("onerror type:", page.evaluate("typeof window.onerror"))
    print("__reflex_otel:", page.evaluate("typeof window.__reflex_otel"))
    # wait for the batch span processor to attempt an export and fail
    page.wait_for_timeout(WAIT * 1000)
    # now manually verify the reflex pipeline works at all
    page.evaluate("""() => {
        const e = new Error('probe manual error'); e.name = 'ProbeError';
        window.onerror(e.message, null, null, null, e);
    }""")
    page.wait_for_timeout(2000)
    ctx.close(); b.close()

for c in console:
    if "PROBE" in c or "Otel" in c or "otel" in c:
        print(c[:300])
print("--- all console types ---")
for c in console:
    print(c[:200])
