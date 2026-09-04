"""Raw browser WebSocket -> Reflex backend round trip, with/without permessage-deflate."""

from __future__ import annotations

import json
import sys
import threading
import time
import uuid
from pathlib import Path

import uvicorn
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent))
from latency_app import BenchApp
from latency_browser import launch_chromium

from reflex.testing import AppHarness

HERE = Path(__file__).parent

PROBE_JS = """
async ({port, token, incName, n, gap, protocol}) => {
  const ws = protocol ? new WebSocket(`ws://127.0.0.1:${port}/_event/?EIO=4&transport=websocket&token=${token}`, [protocol]) : new WebSocket(`ws://127.0.0.1:${port}/_event/?EIO=4&transport=websocket&token=${token}`);
  const q = [];
  let waiter = null;
  ws.onmessage = (e) => { const t = performance.now(); if (waiter) { const w = waiter; waiter = null; w([t, e.data]); } else q.push([t, e.data]); };
  const next = () => new Promise((res) => { if (q.length) res(q.shift()); else waiter = res; });
  await new Promise((res) => ws.onopen = res);
  await next(); // 0{sid}
  ws.send("40/_event,");
  await next(); // 40/_event,{sid}
  const ext = ws.extensions;
  const ev = (name) => "42/_event," + JSON.stringify(["event", {token, name, router_data: {pathname: "/", asPath: "/"}}]);
  ws.send(ev("reflex___state____state.hydrate"));
  await next();
  await new Promise(r => setTimeout(r, 200));
  q.length = 0;
  const rtts = [];
  for (let i = 0; i < n; i++) {
    if (gap) await new Promise(r => setTimeout(r, gap));
    const t0 = performance.now();
    ws.send(ev(incName));
    const [t1, data] = await next();
    rtts.push(t1 - t0);
  }
  ws.close();
  rtts.sort((a, b) => a - b);
  return {extensions: ext, protocol: ws.protocol, median: rtts[Math.floor(n / 2)], p90: rtts[Math.floor(n * 0.9)], min: rtts[0]};
}
"""


def run_backend(harness, per_message_deflate: bool):
    harness.backend = uvicorn.Server(
        uvicorn.Config(
            app=harness.app_asgi,
            host="127.0.0.1",
            port=0,
            ws_per_message_deflate=per_message_deflate,
        )
    )
    harness.backend.shutdown = harness._get_backend_shutdown_handler()
    import contextvars

    ctx = contextvars.copy_context()
    harness.backend_thread = threading.Thread(
        target=lambda: ctx.run(harness.backend.run)
    )
    harness.backend_thread.start()
    return harness._poll_for_servers(timeout=30).getsockname()[1]


def stop_backend(harness):
    harness.backend.should_exit = True
    harness.backend_thread.join()


def main():
    root = HERE / "app_rtt"
    root.mkdir(exist_ok=True)
    harness = AppHarness.create(root=root, app_source=BenchApp)
    harness._initialize_app()
    app_instance = harness.app_instance
    assert app_instance is not None
    inc_name = next(
        k
        for k in app_instance._registration_context.event_handlers
        if k.endswith(".inc")
    )
    out = {}
    with sync_playwright() as pw:
        browser = launch_chromium(pw)
        page = browser.new_page()
        page.goto("about:blank")
        from reflex import constants

        version = constants.Reflex.VERSION
        for deflate, gap, proto in (
            (True, 100, None),
            (True, 100, version),
            (True, 0, version),
        ):
            port = run_backend(harness, deflate)
            time.sleep(0.5)
            res = page.evaluate(
                PROBE_JS,
                {
                    "port": port,
                    "token": str(uuid.uuid4()),
                    "incName": inc_name,
                    "n": 60 if gap else 100,
                    "gap": gap,
                    "protocol": proto,
                },
            )
            out[f"raw_ws_deflate={deflate}_gap={gap}ms_subprotocol={proto}"] = {
                k: (round(v, 2) if isinstance(v, float) else v) for k, v in res.items()
            }
            print(out, flush=True)
            stop_backend(harness)
        browser.close()
    (HERE / "report_ws_probe.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
