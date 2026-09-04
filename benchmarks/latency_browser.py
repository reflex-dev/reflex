"""Measure Reflex latency: cold load, navigation, event round trip, server breakdown."""

from __future__ import annotations

import functools
import json
import statistics
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent))
from latency_app import BenchApp
from reflex_base.config import get_config

from reflex.testing import AppHarness, AppHarnessProd

MODE = sys.argv[1] if len(sys.argv) > 1 else "prod"
LATENCY_MS = (
    int(sys.argv[2]) if len(sys.argv) > 2 else 0
)  # emulated RTT via TCP delay proxy (prod only)
N_LOAD = 5
N_NAV = 6
N_EVENT = 30
_TIMERS = None  # ServerTimers of the current run, read by run_events()

INIT_SCRIPT = r"""
(() => {
  const marks = [];
  window.__marks = marks;
  const mark = (name, extra) => marks.push({name, t: performance.now(), wall: Date.now(), ...(extra || {})});
  window.__mark = mark;
  mark("init");
  // JS-level websocket timing on the real page.
  const origSend = WebSocket.prototype.send;
  WebSocket.prototype.send = function (data) {
    if (this.url.includes("_event") && typeof data === "string" && data.startsWith("42")) mark("ws_send", {text: data.slice(0, 60)});
    return origSend.call(this, data);
  };
  const origAdd = WebSocket.prototype.addEventListener;
  const hook = (ws) => {
    if (ws.__hooked || !ws.url.includes("_event")) return;
    ws.__hooked = true;
    origAdd.call(ws, "message", (e) => { if (typeof e.data === "string" && e.data.startsWith("42")) mark("ws_recv", {text: e.data.slice(0, 60)}); }, {capture: true});
  };
  WebSocket.prototype.addEventListener = function (type, ...rest) { hook(this); return origAdd.call(this, type, ...rest); };
  const onmsg = Object.getOwnPropertyDescriptor(WebSocket.prototype, "onmessage");
  Object.defineProperty(WebSocket.prototype, "onmessage", {set(fn) { hook(this); onmsg.set.call(this, fn); }, get() { return onmsg.get.call(this); }});
  document.addEventListener("click", (e) => {
    const el = e.target.closest("[id]");
    mark("click", {id: el ? el.id : null});
  }, true);
  const origPush = history.pushState;
  history.pushState = function (...args) { mark("pushState", {url: String(args[2])}); return origPush.apply(this, args); };
  const seen = new Set();
  const scan = (root) => {
    if (!root.querySelectorAll) return;
    for (const el of root.querySelectorAll("[id]")) {
      const id = el.id;
      if (id.startsWith("page-") || id === "hydrated" || id === "loading" || id === "loaded_at") {
        const key = id + "|" + el.textContent;
        if (!seen.has(key)) { seen.add(key); mark("dom", {id, text: el.textContent}); }
      }
    }
  };
  const obs = new MutationObserver((muts) => {
    for (const m of muts) {
      if (m.type === "characterData") {
        const el = m.target.parentElement;
        if (el && el.id) mark("text", {id: el.id, text: el.textContent});
        continue;
      }
      if (m.type === "attributes") {
        if (m.target.id) mark("attr", {id: m.target.id, text: m.target.textContent});
        continue;
      }
      for (const n of m.addedNodes) {
        if (n.nodeType === 1) { scan(n); if (n.id) scan({querySelectorAll: () => [n]}); }
      }
      if (m.target && m.target.id === "counter") mark("text", {id: "counter", text: m.target.textContent});
    }
  });
  const start = () => { obs.observe(document.documentElement, {childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ["id"]}); };
  if (document.documentElement) start(); else document.addEventListener("DOMContentLoaded", start);
})();
"""


def launch_chromium(pw):
    """Launch headless Chromium, honoring ``BENCH_CHROMIUM`` for a custom executable.

    Returns:
        The Playwright browser.
    """
    import os

    exe = os.environ.get("BENCH_CHROMIUM")
    if exe is None:
        fallback = Path("/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
        exe = str(fallback) if fallback.exists() else None
    return pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()


def first_id(marks, origin, id_, need_text=False):
    for m in marks:
        if (
            m["name"] in ("dom", "text", "attr")
            and m.get("id") == id_
            and (not need_text or m.get("text"))
        ):
            return round(m["t"] - origin, 1)
    return None


def median(xs):
    return round(statistics.median(xs), 1) if xs else None


def p90(xs):
    if not xs:
        return None
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(len(xs) * 0.9))], 1)


class ServerTimers:
    """Monkeypatch hot-path methods to record wall time per call."""

    def __init__(self, harness):
        """Patch the running app inside ``harness``."""
        self.samples: dict[str, list[float]] = {}
        self._lag_started = False
        self.patch(harness)

    def rec(self, name, dt):
        """Record one sample (seconds) under ``name``."""
        self.samples.setdefault(name, []).append(dt * 1000)

    def wrap_async(self, obj, attr, name):
        """Wrap the coroutine method ``attr`` of ``obj`` to time each call."""
        orig = getattr(obj, attr)

        @functools.wraps(orig)
        async def wrapper(*a, **kw):
            t0 = time.perf_counter()
            try:
                return await orig(*a, **kw)
            finally:
                self.rec(name, time.perf_counter() - t0)

        setattr(obj, attr, wrapper)

    def patch(self, harness):
        """Install all timers on the hot path of the given harness."""
        from reflex_base.event.processor.base_state_processor import (
            BaseStateEventProcessor,
        )

        from reflex.state import BaseState

        self.wrap_async(
            BaseStateEventProcessor, "_execute_event", "server.execute_event"
        )
        self.wrap_async(BaseState, "_get_resolved_delta", "server.get_delta")
        sm = harness.app_instance.state_manager
        self.wrap_async(type(sm), "get_state", "server.state_manager.get_state")
        self.wrap_async(type(sm), "set_state", "server.state_manager.set_state")
        ns = harness.app_instance.event_namespace
        self.wrap_async(ns, "on_event", "server.on_event_total")
        self.wrap_async(ns, "emit_update", "server.emit_update")
        # Span from event arrival to delta emitted (single sequential client => pair by order).
        self.arrivals: list[float] = []
        self.emits: list[float] = []
        orig_on_event = ns.on_event
        orig_emit = ns.emit_update

        self.arrivals_wall: list[float] = []
        self.emits_wall: list[float] = []

        async def on_event_span(*a, **kw):
            self.arrivals.append(time.perf_counter())
            self.arrivals_wall.append(time.time() * 1000)
            return await orig_on_event(*a, **kw)

        async def emit_span(*a, **kw):
            r = await orig_emit(*a, **kw)
            self.emits.append(time.perf_counter())
            self.emits_wall.append(time.time() * 1000)
            return r

        ns.on_event = on_event_span
        ns.emit_update = emit_span
        from reflex_base.event.processor.event_processor import EventProcessor

        self.wrap_async(EventProcessor, "enqueue", "server.enqueue")
        # Wall time when uvicorn actually performs the ASGI websocket.send of a delta frame.
        self.asgi_send_wall: list[float] = []
        import uvicorn.protocols.websockets.websockets_sansio_impl as sansio

        orig_send = sansio.WebSocketsSansIOProtocol.send

        async def asgi_send(proto, message):
            if message.get("type") == "websocket.send" and '"delta"' in (
                message.get("text") or ""
            ):
                self.asgi_send_wall.append(time.time() * 1000)
            return await orig_send(proto, message)

        sansio.WebSocketsSansIOProtocol.send = asgi_send  # pyright: ignore[reportAttributeAccessIssue]
        # Event-loop lag monitor on the backend loop.
        self.loop_lags: list[tuple[float, float]] = []
        import asyncio

        async def lag_monitor():
            while True:
                t0 = time.perf_counter()
                await asyncio.sleep(0.001)
                lag = (time.perf_counter() - t0) * 1000 - 1
                if lag > 2:
                    self.loop_lags.append((time.time() * 1000, round(lag, 1)))

        self.lag_monitor = lag_monitor
        app = harness.app_instance
        orig_startup = app.event_namespace.on_connect

        async def on_connect_hook(*a, **kw):
            if not self._lag_started:
                self._lag_started = True
                asyncio.get_running_loop().create_task(lag_monitor())
            return await orig_startup(*a, **kw)

        app.event_namespace.on_connect = on_connect_hook
        self.state_manager_type = type(sm).__name__

    def report(self):
        """Summarize the recorded samples.

        Returns:
            Per-timer median, p90 and max in milliseconds, plus sample counts.
        """
        spans = []
        for t_emit in self.emits:
            prev = [t for t in self.arrivals if t < t_emit]
            if prev:
                spans.append((t_emit - prev[-1]) * 1000)
        if spans:
            self.samples["server.span_arrival_to_emit"] = spans
        return {
            k: {
                "n": len(v),
                "median_ms": median(v),
                "p90_ms": p90(v),
                "max_ms": round(max(v), 1),
            }
            for k, v in sorted(self.samples.items())
        }


class WsLog:
    """Websocket frames with browser-side CDP monotonic timestamps (seconds)."""

    def __init__(self):
        """Create an empty frame log."""
        self.frames = []
        self.opened = []
        self.event_ws_ids = set()

    def attach(self, page, context):
        """Subscribe to CDP websocket frame events for ``page``."""
        cdp = context.new_cdp_session(page)
        cdp.send("Network.enable")

        def created(ev):
            if "_event" in ev.get("url", ""):
                self.event_ws_ids.add(ev["requestId"])
                self.opened.append(time.perf_counter())

        def sent(ev):
            if ev["requestId"] in self.event_ws_ids:
                self.frames.append((
                    "sent",
                    ev["timestamp"],
                    ev["response"]["payloadData"],
                ))

        def recv(ev):
            if ev["requestId"] in self.event_ws_ids:
                self.frames.append((
                    "recv",
                    ev["timestamp"],
                    ev["response"]["payloadData"],
                ))

        cdp.on("Network.webSocketCreated", created)
        cdp.on("Network.webSocketFrameSent", sent)
        cdp.on("Network.webSocketFrameReceived", recv)
        self.cdp = cdp


def frames_since(wslog, idx):
    return wslog.frames[idx:]


def summarize_frames(frames):
    out = []
    for direction, t, payload in frames:
        p = payload if isinstance(payload, str) else payload.decode(errors="replace")
        kind = p[:2]
        name = ""
        if direction == "sent":
            if ".hydrate" in p[:200]:
                name = "hydrate"
            elif "on_load_internal" in p[:200]:
                name = "on_load_internal"
            elif '"name"' in p:
                name = "event"
        elif '"delta"' in p:
            name = "delta(is_hydrated)" if "is_hydrated_rx_state_" in p else "delta"
        out.append((direction, t, kind, name, len(p)))
    return out


def run_cold_load(page, url, wslog, context):
    results = []
    for i in range(N_LOAD):
        context.clear_cookies()
        # Clear cache via CDP.
        cdp = context.new_cdp_session(page)
        cdp.send("Network.clearBrowserCache")
        cdp.detach()
        f0 = len(wslog.frames)
        t0 = time.perf_counter()
        page.goto(url)
        page.wait_for_selector("#hydrated", timeout=30000, state="attached")
        marks = page.evaluate("window.__marks")
        nav = page.evaluate(
            "JSON.parse(JSON.stringify(performance.getEntriesByType('navigation')[0]))"
        )
        res = page.evaluate(
            "performance.getEntriesByType('resource').map(r => ({n: r.name, type: r.initiatorType, size: r.transferSize, enc: r.encodedBodySize, dec: r.decodedBodySize, end: r.responseEnd}))"
        )
        origin = nav["startTime"]

        def first(name, marks=marks, origin=origin, **filt):
            for m in marks:
                if m["name"] == name and all(m.get(k) == v for k, v in filt.items()):
                    return round(m["t"] - origin, 1)
            return None

        frames = summarize_frames(frames_since(wslog, f0))
        if i == 0:
            (Path(__file__).parent / f"frames_{MODE}_{LATENCY_MS}.txt").write_text(
                "\n".join(
                    f"{d} +{(t - frames[0][1]) * 1000:.1f}ms kind={k} name={n} len={length}"
                    for d, t, k, n, length in frames
                )
                + "\n\nMARKS\n"
                + "\n".join(json.dumps(m) for m in marks)
            )
        ws_open = round((wslog.opened[-1] - t0) * 1000, 1) if wslog.opened else None
        hyd_sent_t = next(
            (t for d, t, _k, n, _length in frames if d == "sent" and n == "hydrate"),
            None,
        )

        def frame_t(direction, name, frames=frames, hyd_sent_t=hyd_sent_t):
            # milliseconds after the hydrate frame was sent (browser clock)
            for d, t, _k, n, _length in frames:
                if d == direction and n == name and hyd_sent_t is not None:
                    return round((t - hyd_sent_t) * 1000, 1)
            return None

        def frame_len(direction, name, frames=frames):
            for d, _t, _k, n, length in frames:
                if d == direction and n == name:
                    return length
            return None

        js = [r for r in res if r["n"].endswith(".js") or ".js?" in r["n"]]
        results.append({
            "responseStart": round(nav["responseStart"], 1),
            "domContentLoaded": round(nav["domContentLoadedEventEnd"], 1),
            "loadEvent": round(nav["loadEventEnd"], 1),
            "react_mounted(page marker)": first_id(marks, origin, "page-index"),
            "ws_open(approx)": ws_open,
            "hydrate_delta_recv(+ms after hydrate sent)": frame_t(
                "recv", "delta(is_hydrated)"
            ),
            "onload_delta_recv(+ms after hydrate sent)": (
                lambda r: r[1] if len(r) > 1 else None
            )([
                round((t - hyd_sent_t) * 1000, 1)
                for d, t, _k, n, _length in frames
                if d == "recv" and n.startswith("delta") and hyd_sent_t
            ]),
            "dom_hydrated": first_id(marks, origin, "hydrated"),
            "hydrate_delta_bytes": frame_len("recv", "delta(is_hydrated)"),
            "js_files": len(js),
            "js_transfer_kb": round(sum(r["size"] for r in js) / 1024, 1),
            "js_decoded_kb": round(sum(r["dec"] for r in js) / 1024, 1),
            "total_requests": len(res) + 1,
            "total_transfer_kb": round(
                (sum(r["size"] for r in res) + nav["transferSize"]) / 1024, 1
            ),
        })
    return results


def run_warm_reload(page, url, wslog):
    results = []
    for _i in range(N_LOAD):
        len(wslog.frames)
        time.perf_counter()
        page.goto(url)
        page.wait_for_selector("#hydrated", timeout=30000, state="attached")
        marks = page.evaluate("window.__marks")
        nav = page.evaluate(
            "JSON.parse(JSON.stringify(performance.getEntriesByType('navigation')[0]))"
        )
        origin = nav["startTime"]
        hyd = first_id(marks, origin, "hydrated")
        mounted = first_id(marks, origin, "page-index")
        results.append({
            "domContentLoaded": round(nav["domContentLoadedEventEnd"], 1),
            "react_mounted": round(mounted, 1) if mounted else None,
            "dom_hydrated": round(hyd, 1) if hyd else None,
        })
    return results


def run_navigation(page, wslog, target: str, marker: str, wait_hydrated: bool):
    results = []
    for _i in range(N_NAV):
        # Always start from index.
        if not page.url.endswith("/") or page.locator("#page-index").count() == 0:
            page.click("#nav-index")
            page.wait_for_selector("#page-index", state="attached")
            page.wait_for_selector("#hydrated", state="attached")
        page.evaluate("window.__marks.length = 0")
        f0 = len(wslog.frames)
        r0 = page.evaluate("performance.getEntriesByType('resource').length")
        page.click(f"#nav-{target}")
        page.wait_for_selector(f"#page-{marker}", state="attached")
        if wait_hydrated:
            page.wait_for_selector("#hydrated", state="attached")
            if target.startswith("loaded"):
                page.wait_for_function(
                    "document.querySelector('#loaded_at') && document.querySelector('#loaded_at').textContent.length > 0"
                )
        page.wait_for_timeout(50)
        marks = page.evaluate("window.__marks")
        new_res = page.evaluate(
            f"performance.getEntriesByType('resource').slice({r0}).map(r => ({{n: r.name.split('/').pop(), size: r.transferSize, dur: r.duration}}))"
        )
        click_t = next((m["t"] for m in marks if m["name"] == "click"), None)

        def rel(pred, marks=marks, click_t=click_t):
            for m in marks:
                if pred(m):
                    return round(m["t"] - click_t, 1)
            return None

        frames = summarize_frames(frames_since(wslog, f0))
        # websocket relative times, using python clock aligned to the click via first sent frame
        sent = [(t, n) for d, t, _k, n, _length in frames if d == "sent" and n]
        recv = [(t, n) for d, t, _k, n, _length in frames if d == "recv" and n]
        ws_rtt = None
        if sent and recv:
            ws_rtt = round((recv[-1][0] - sent[0][0]) * 1000, 1)
        results.append({
            "pushState": rel(lambda m: m["name"] == "pushState"),
            "unhydrated(loading shown)": first_id(marks, click_t, "loading"),
            "new_page_mounted": first_id(marks, click_t, f"page-{marker}"),
            "hydrated_again": first_id(marks, click_t, "hydrated"),
            "on_load_data_shown": first_id(marks, click_t, "loaded_at", need_text=True),
            "ws_first_sent_to_last_recv": ws_rtt,
            "ws_frames_sent": len(sent),
            "ws_frames_recv": len(recv),
            "chunk_requests": len(new_res),
            "chunk_kb": round(sum(r["size"] for r in new_res) / 1024, 1),
        })
    return results


def run_events(page, wslog):
    page.click("#nav-index")
    page.wait_for_selector("#page-index", state="attached")
    page.wait_for_selector("#hydrated", state="attached")
    results = []
    for i in range(N_EVENT):
        before = page.locator("#counter").inner_text()
        page.evaluate("window.__marks.length = 0")
        f0 = len(wslog.frames)
        if "synthetic" in sys.argv:
            page.evaluate("document.querySelector('#inc').click()")
        else:
            page.click("#inc")
        page.wait_for_function(
            f"document.querySelector('#counter').textContent !== '{before}'"
        )
        marks = page.evaluate("window.__marks")
        click_t = next(m["t"] for m in marks if m["name"] == "click")
        upd = next(
            (m["t"] for m in marks if m["name"] == "text" and m.get("id") == "counter"),
            None,
        )
        frames = frames_since(wslog, f0)
        sent = [t for d, t, _p in frames if d == "sent"]
        recv = [t for d, t, _p in frames if d == "recv"]
        if i < 3:
            with (Path(__file__).parent / f"event_frames_{MODE}_{LATENCY_MS}.txt").open(
                "a"
            ) as fh:
                fh.write(
                    f"--- event {i} click_t={click_t}\n"
                    + "\n".join(
                        f"{d} +{(t - frames[0][1]) * 1000:.2f}ms {p[:200]}"
                        for d, t, p in frames
                    )
                    + "\n"
                )
        js_send = next((m["t"] for m in marks if m["name"] == "ws_send"), None)
        js_recv = next((m["t"] for m in marks if m["name"] == "ws_recv"), None)
        send_wall = next((m["wall"] for m in marks if m["name"] == "ws_send"), None)
        recv_wall = next((m["wall"] for m in marks if m["name"] == "ws_recv"), None)
        timers = _TIMERS
        assert timers is not None
        arr = [w for w in timers.arrivals_wall if send_wall and w >= send_wall - 2]
        emt = [w for w in timers.emits_wall if send_wall and w >= send_wall - 2]
        arrival = arr[0] if arr else None
        emitted = emt[0] if emt else None
        asgi = [w for w in timers.asgi_send_wall if send_wall and w >= send_wall - 2]
        asgi_t = asgi[0] if asgi else None
        lags = [
            (round(w - send_wall, 1), lag)
            for w, lag in timers.loop_lags
            if send_wall and send_wall - 2 <= w <= (recv_wall or send_wall + 50) + 2
        ]
        results.append({
            "click_to_dom_update": round(upd - click_t, 1) if upd else None,
            "js: click_to_ws_send": round(js_send - click_t, 1) if js_send else None,
            "js: ws_send_to_ws_recv": round(js_recv - js_send, 1)
            if js_send and js_recv
            else None,
            "js: ws_recv_to_dom": round(upd - js_recv, 1) if js_recv and upd else None,
            "wall: browser_send_to_server_arrival": round(arrival - send_wall, 1)
            if arrival and send_wall
            else None,
            "wall: server_arrival_to_emit": round(emitted - arrival, 1)
            if arrival and emitted
            else None,
            "wall: server_emit_to_browser_recv": round(recv_wall - emitted, 1)
            if emitted and recv_wall
            else None,
            "wall: server_emit_to_asgi_send": round(asgi_t - emitted, 1)
            if emitted and asgi_t
            else None,
            "wall: asgi_send_to_browser_recv": round(recv_wall - asgi_t, 1)
            if asgi_t and recv_wall
            else None,
            "loop_lags_during(ms after send, lag)": lags,
            "ws_sent_to_recv": round((recv[0] - sent[0]) * 1000, 1)
            if sent and recv
            else None,
            "event_bytes": len(frames[0][2]) if frames else None,
            "delta_bytes": next((len(p) for d, _t, p in frames if d == "recv"), None),
        })
        page.wait_for_timeout(20)
    return results


def run_typing(page, wslog):
    page.click("#nav-form")
    page.wait_for_selector("#page-form", state="attached")
    page.wait_for_selector("#hydrated", state="attached")
    page.evaluate("window.__marks.length = 0")
    f0 = len(wslog.frames)
    t0 = time.perf_counter()
    page.type("#text", "hello world benchmark", delay=30)
    page.wait_for_function(
        "document.querySelector('#text_out').textContent === 'hello world benchmark'"
    )
    t1 = time.perf_counter()
    frames = frames_since(wslog, f0)
    return {
        "chars": 21,
        "typing_wall_ms": round((t1 - t0) * 1000, 1),
        "ws_frames_sent": sum(1 for d, _t, _p in frames if d == "sent"),
        "ws_frames_recv": sum(1 for d, _t, _p in frames if d == "recv"),
    }


def agg(rows):
    if not rows:
        return {}
    keys = rows[0].keys()
    out = {}
    for k in keys:
        vals = [r[k] for r in rows if isinstance(r.get(k), (int, float))]
        if vals:
            out[k] = {"median": median(vals), "p90": p90(vals)}
        elif isinstance(rows[0].get(k), list):
            out[k] = [r[k] for r in rows[:5]]
        else:
            out[k] = None
    return out


def bundle_stats(app_path: Path):
    client = app_path / ".web" / "build" / "client"
    if not client.exists():
        return None
    js = sorted(client.rglob("*.js"), key=lambda p: p.stat().st_size, reverse=True)
    js = [p for p in js if not p.name.endswith((".gz", ".br", ".zst"))]
    gz = list(client.rglob("*.js.gz"))
    return {
        "js_files": len(js),
        "js_total_kb": round(sum(p.stat().st_size for p in js) / 1024, 1),
        "js_gz_total_kb": round(sum(p.stat().st_size for p in gz) / 1024, 1)
        if gz
        else None,
        "largest": [(p.name, round(p.stat().st_size / 1024, 1)) for p in js[:8]],
        "html_files": len(list(client.rglob("*.html"))),
    }


def main():
    root = Path(__file__).parent / f"app_{MODE}"
    root.mkdir(exist_ok=True)
    harness_cls = AppHarnessProd if MODE == "prod" else AppHarness
    t_start = time.perf_counter()
    report: dict = {"mode": MODE, "emulated_latency_ms": LATENCY_MS}
    with harness_cls.create(root=root, app_source=BenchApp) as harness:
        report["harness_startup_s"] = round(time.perf_counter() - t_start, 1)
        timers = ServerTimers(harness)
        report["state_manager"] = timers.state_manager_type
        url = harness.frontend_url
        assert url
        if LATENCY_MS:
            from urllib.parse import urlsplit

            from latency_delay_proxy import DelayProxy

            api = urlsplit(get_config().api_url)
            fe = urlsplit(url)
            assert api.port is not None
            assert fe.port is not None
            be_proxy = DelayProxy(api.port, LATENCY_MS / 2).start()
            fe_proxy = DelayProxy(fe.port, LATENCY_MS / 2).start()
            client = harness.app_path / ".web" / "build" / "client"
            for f in client.rglob("reflex-env-*"):
                if f.suffix in (".gz", ".br", ".zst"):
                    f.unlink()
                else:
                    f.write_text(
                        f.read_text().replace(
                            f"127.0.0.1:{api.port}", f"127.0.0.1:{be_proxy}"
                        )
                    )
            url = f"http://127.0.0.1:{fe_proxy}/"
            report["proxied_url"] = url
        with sync_playwright() as pw:
            browser = launch_chromium(pw)
            context = browser.new_context()
            context.add_init_script(INIT_SCRIPT)
            page = context.new_page()
            wslog = WsLog()
            wslog.attach(page, context)
            # Warm the dev server / prime everything once.
            page.goto(url)
            page.wait_for_selector("#hydrated", timeout=120000, state="attached")
            for t in ["table", "loaded", "loaded_fast", "static", "form"]:
                page.click(f"#nav-{t}")
                page.wait_for_selector(f"#page-{t}", timeout=60000, state="attached")
            page.click("#nav-index")
            page.wait_for_selector("#hydrated", state="attached")

            global _TIMERS
            _TIMERS = timers
            if "events_only" in sys.argv:
                import uuid
                from urllib.parse import urlsplit

                from latency_ws_probe import PROBE_JS

                app_instance = harness.app_instance
                assert app_instance is not None
                inc_name = next(
                    k
                    for k in app_instance._registration_context.event_handlers
                    if k.endswith(".inc")
                )
                api_port = urlsplit(get_config().api_url).port
                report["raw_ws_probe_inside_real_page"] = {
                    f"gap={gap}": page.evaluate(
                        PROBE_JS,
                        {
                            "port": api_port,
                            "token": str(uuid.uuid4()),
                            "incName": inc_name,
                            "n": 40,
                            "gap": gap,
                        },
                    )
                    for gap in (0, 100)
                }
                cdp = wslog.cdp
                if "trace" in sys.argv:
                    trace_events = []
                    cdp.on(
                        "Tracing.dataCollected",
                        lambda ev: trace_events.extend(ev["value"]),
                    )
                    done = {"ok": False}
                    cdp.on("Tracing.tracingComplete", lambda ev: done.update(ok=True))
                    cdp.send(
                        "Tracing.start",
                        {
                            "categories": "devtools.timeline,disabled-by-default-devtools.timeline,blink.user_timing,v8.execute",
                            "transferMode": "ReportEvents",
                        },
                    )
                    page.click("#nav-index")
                    for _ in range(8):
                        before = page.locator("#counter").inner_text()
                        page.click("#inc")
                        page.wait_for_function(
                            f"document.querySelector('#counter').textContent !== '{before}'"
                        )
                        page.wait_for_timeout(100)
                    cdp.send("Tracing.end")
                    while not done["ok"]:
                        page.wait_for_timeout(50)
                    # main-thread renderer events: aggregate by name (complete events with dur), top 20 by total
                    agg_: dict = {}
                    for ev in trace_events:
                        if (
                            ev.get("ph") == "X"
                            and "dur" in ev
                            and ev.get("cat", "").find("devtools.timeline") >= 0
                        ):
                            agg_[ev["name"]] = agg_.get(ev["name"], 0) + ev["dur"]
                    report["trace_main_thread_ms_total_over_8_clicks"] = {
                        k: round(v / 1000, 1)
                        for k, v in sorted(agg_.items(), key=lambda kv: -kv[1])[:20]
                    }
                    # per click: list of tasks >0.5ms between the ws send and recv
                    sorted(
                        ev["ts"]
                        for ev in trace_events
                        if ev.get("name") == "WebSocketSend"
                        or (ev.get("name") == "WebSocketSendHandshakeRequest")
                    )
                    report["trace_note"] = (
                        "durations are wall ms summed across 8 real clicks (input dispatch, style, layout, paint, JS)"
                    )
                cdp.send("Profiler.enable")
                cdp.send("Profiler.setSamplingInterval", {"interval": 100})
                cdp.send("Profiler.start")
                report["event_roundtrip"] = agg(run_events(page, wslog))
                prof = cdp.send("Profiler.stop")["profile"]
                nodes = {n["id"]: n for n in prof["nodes"]}
                deltas = prof["timeDeltas"]
                self_us: dict = {}
                for sample, dt in zip(prof["samples"], deltas, strict=False):
                    n = nodes[sample]
                    cf = n["callFrame"]
                    key = f"{cf['functionName'] or '(anon)'} @ {cf['url'].split('/')[-1]}:{cf['lineNumber']}"
                    self_us[key] = self_us.get(key, 0) + dt
                total = sum(self_us.values())
                top = sorted(self_us.items(), key=lambda kv: -kv[1])[:25]
                report["profile_top_self_ms"] = {k: round(v / 1000, 1) for k, v in top}
                report["profile_total_ms"] = round(total / 1000, 1)
                # also aggregate by script url
                by_url: dict = {}
                for sample, dt in zip(prof["samples"], deltas, strict=False):
                    url = (
                        nodes[sample]["callFrame"]["url"].split("/")[-1]
                        or "(native/idle)"
                    )
                    by_url[url] = by_url.get(url, 0) + dt
                report["profile_by_script_ms"] = {
                    k: round(v / 1000, 1)
                    for k, v in sorted(by_url.items(), key=lambda kv: -kv[1])[:12]
                }
                browser.close()
                report["server_timers"] = timers.report()
                print(json.dumps(report, indent=2))
                return
            report["cold_load"] = agg(run_cold_load(page, url, wslog, context))
            report["warm_reload"] = agg(run_warm_reload(page, url, wslog))
            report["nav"] = {
                "index->table (100 rows, no on_load)": agg(
                    run_navigation(page, wslog, "table", "table", True)
                ),
                "index->loaded_fast (on_load, no IO)": agg(
                    run_navigation(page, wslog, "loaded_fast", "loaded_fast", True)
                ),
                "index->loaded (on_load, 20ms IO)": agg(
                    run_navigation(page, wslog, "loaded", "loaded", True)
                ),
                "index->static (no state on page)": agg(
                    run_navigation(page, wslog, "static", "static", False)
                ),
            }
            report["event_roundtrip"] = agg(run_events(page, wslog))
            report["typing_21_chars"] = run_typing(page, wslog)
            browser.close()
        report["server_timers"] = timers.report()
        report["bundle"] = bundle_stats(harness.app_path)
    out = Path(__file__).parent / f"report_{MODE}_{LATENCY_MS}ms.json"
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
