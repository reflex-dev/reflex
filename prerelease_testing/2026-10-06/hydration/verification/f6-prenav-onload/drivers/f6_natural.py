"""F6 realism: no route_web_socket hold. Page loaded through upgrade_delay_proxy; click the client-side link
CLICK_DELAY ms after React has attached its handlers (models human reaction time after the page is interactive).
In-page instrumentation timestamps (performance.now): websocket creation/open, the socket.io CONNECT (`40...`) send,
and the click. A run is in the F6 window when the CONNECT is sent AFTER the click.

Usage: f6_natural.py BASE LABEL OUT_JSON RUNS CLICK_DELAYS_CSV [start_path] [link_sel] [target_path]
"""
import json
import sys

from playwright.sync_api import sync_playwright

assert "/envs/driver/" in sys.executable, sys.executable
base, label, out, runs = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
click_delays = [int(x) for x in sys.argv[5].split(",")]
start = sys.argv[6] if len(sys.argv) > 6 else "/items/1"
link = sys.argv[7] if len(sys.argv) > 7 else "#nav-item2"
target = sys.argv[8] if len(sys.argv) > 8 else "/items/2"

INIT = r"""
(() => {
  window.__f6 = {ws: [], sends: [], clicks: []};
  const OrigWS = window.WebSocket;
  const origSend = OrigWS.prototype.send;
  OrigWS.prototype.send = function (data) {
    try {
      if (typeof data === 'string' && data.startsWith('40'))
        window.__f6.sends.push([performance.now(), data.slice(0, 400)]);
    } catch (e) {}
    return origSend.call(this, data);
  };
  window.WebSocket = function (url, protocols) {
    const ws = protocols === undefined ? new OrigWS(url) : new OrigWS(url, protocols);
    const rec = {url: String(url).slice(0, 80), created: performance.now(), open: null};
    window.__f6.ws.push(rec);
    ws.addEventListener('open', () => { rec.open = performance.now(); });
    return ws;
  };
  window.WebSocket.prototype = OrigWS.prototype;
  Object.assign(window.WebSocket, {CONNECTING: 0, OPEN: 1, CLOSING: 2, CLOSED: 3});
  document.addEventListener('click', e => window.__f6.clicks.push([performance.now(), (e.target && e.target.id) || '']), true);
})();
"""

INTERACTIVE = "(sel) => { const a = document.querySelector(sel); return !!a && Object.keys(a).some(k => k.startsWith('__reactProps')); }"

res = []
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for cd in click_delays:
        for i in range(runs):
            ctx = b.new_context()
            ctx.add_init_script(INIT)
            p = ctx.new_page()
            p.goto(base + start, wait_until="commit")
            p.wait_for_function(INTERACTIVE, arg=link, timeout=20000, polling=5)
            t_interactive = p.evaluate("performance.now()")
            if cd:
                p.wait_for_timeout(cd)
            p.click(link)
            if target == "*":  # do not assume the destination; record where the user ends up
                p.wait_for_timeout(1000)
                p.wait_for_function(
                    "() => document.getElementById('hyd-flag') && document.getElementById('hyd-flag').textContent === 'H:yes'",
                    timeout=20000)
            else:
                p.wait_for_function(
                    "(t) => document.getElementById('hyd-flag') && document.getElementById('hyd-flag').textContent === 'H:yes' && location.pathname === t",
                    arg=target, timeout=20000)
            p.wait_for_timeout(1500)
            final_path = p.evaluate("location.pathname")
            f6 = p.evaluate("window.__f6")
            try:
                trace = json.loads(p.inner_text("#trace"))
            except Exception:  # noqa: BLE001
                trace = None
            t_click = f6["clicks"][0][0] if f6["clicks"] else None
            t_connect = f6["sends"][0][0] if f6["sends"] else None
            boot_path = None
            if f6["sends"]:
                s = f6["sends"][0][1]
                k = s.find('"pathname":"')
                boot_path = s[k + 12: s.find('"', k + 12)] if k != -1 else None
            r = {
                "click_delay_ms": cd,
                "run": i,
                "t_interactive": round(t_interactive),
                "t_ws_created": round(f6["ws"][0]["created"]) if f6["ws"] else None,
                "t_ws_open": round(f6["ws"][0]["open"]) if f6["ws"] and f6["ws"][0]["open"] else None,
                "t_click": round(t_click) if t_click else None,
                "t_connect_sent": round(t_connect) if t_connect else None,
                "connect_after_click": (t_connect is not None and t_click is not None and t_connect > t_click),
                "boot_router_pathname": boot_path,
                "trace": trace,
                "final_path": final_path,
            }
            res.append(r)
            print(label, json.dumps(r), flush=True)
            ctx.close()
    b.close()
json.dump(res, open(out, "w"), indent=1)
