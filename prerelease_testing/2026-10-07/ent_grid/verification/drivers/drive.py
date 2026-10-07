r"""Verifier driver for claim H-1 (ent_grid): render-time readers of window.__reflex vs boot hydrate.

Usage (driver venv, proxy bypass on the client side only):
  NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python drivers/drive.py \
      --app entv|corev --url http://localhost:3680 --out out/<run> --server-venv <venv> [--only s1,s2]

Every page gets an init script that (a) traps assignments to window.__reflex with a setter that
records performance.now() and the JS stack (WHERE/WHEN it is assigned), (b) subclasses WebSocket
to record every frame of the reflex event socket with performance.now() timestamps, (c) polls the
AG Grid wrappers every 50 ms and records each change of header/cell counts. The ReflexProbe
component (src/probe.py) pushes one trace entry per render. Output per scenario:
<out>/<scenario>.json (measurements, timeline, console, page errors, parsed boot frames) and
<out>/<scenario>.png.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

assert "/scratchpad/envs/driver/" in sys.executable, sys.executable

from playwright.sync_api import sync_playwright  # noqa: E402

CHROMIUM = "/opt/pw-browsers/chromium"
GRID_WRAPPERS = ["w_state", "w_literal", "w_memo_props", "w_memo_state", "w_onload", "w_state2", "w_detail_state", "w_detail_literal", "w_renderer"]

INIT_JS = r"""
(() => {
  window.__trace = window.__trace || [];
  let _rx;
  Object.defineProperty(window, "__reflex", {
    configurable: true, enumerable: true,
    get() { return _rx; },
    set(v) {
      _rx = v;
      if (window.__reflexSetAt === undefined) window.__reflexSetAt = performance.now();
      window.__trace.push({ev: "__reflex_set", t: performance.now(),
        keys: v ? Object.keys(v).length : null, stack: String(new Error().stack).split("\n").slice(1, 8).join(" | ")});
    },
  });
  const Orig = window.WebSocket;
  class TracedWS extends Orig {
    constructor(...a) {
      super(...a);
      const url = String(a[0]);
      this.__traced = url.includes("_event");
      if (this.__traced) {
        window.__trace.push({ev: "ws_open_call", t: performance.now(), url});
        this.addEventListener("open", () => window.__trace.push({ev: "ws_open", t: performance.now()}));
        this.addEventListener("message", (e) => window.__trace.push({ev: "ws_in", t: performance.now(),
          data: typeof e.data === "string" ? e.data.slice(0, 200000) : "[binary]"}));
      }
    }
    send(d) {
      if (this.__traced) window.__trace.push({ev: "ws_out", t: performance.now(),
        data: typeof d === "string" ? d.slice(0, 200000) : "[binary]"});
      return super.send(d);
    }
  }
  window.WebSocket = TracedWS;
  const ids = %IDS%;
  let last = "";
  const t0 = performance.now();
  const poll = () => {
    const snap = {};
    for (const id of ids) {
      const el = document.getElementById(id);
      if (!el) continue;
      snap[id] = [el.querySelectorAll(".ag-header-cell").length, el.querySelectorAll(".ag-cell").length];
    }
    const key = JSON.stringify(snap);
    if (key !== last) { last = key; window.__trace.push({ev: "grid", t: performance.now(), counts: snap}); }
    if (performance.now() - t0 < 20000) setTimeout(poll, 50);
  };
  setTimeout(poll, 0);
})();
""".replace("%IDS%", json.dumps(GRID_WRAPPERS))

MEASURE_JS = r"""
(ids) => {
  const r = {grids: {}};
  for (const id of ids) {
    const el = document.getElementById(id);
    if (!el) continue;
    r.grids[id] = {
      headers: Array.from(el.querySelectorAll(".ag-header-cell")).map((e) => e.innerText.trim()),
      cells: el.querySelectorAll(".ag-cell").length,
      rows: el.querySelectorAll(".ag-center-cols-container .ag-row").length,
    };
  }
  r.probes = Object.fromEntries(Array.from(document.querySelectorAll("[id^=probe-]")).map((e) => [e.id, e.textContent]));
  r.probeCounts = window.__probeCounts || {};
  r.reflexDefinedNow = typeof window.__reflex !== "undefined";
  r.reflexSetAt = window.__reflexSetAt === undefined ? null : window.__reflexSetAt;
  r.path = location.pathname;
  r.heading = document.getElementById("heading")?.textContent ?? null;
  return r;
}
"""


def server_check(port: int, venv: str) -> dict:
    """Confirm the process listening on `port` runs from the expected venv.

    Args:
        port: The listening port.
        venv: Expected venv name under $SB/envs.

    Returns:
        Info about the listening process(es).
    """
    out = subprocess.run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"], capture_output=True, text=True).stdout.split()
    info = []
    for pid in out:
        try:
            cmd = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode()
        except OSError:
            continue
        info.append({"pid": pid, "cmd": cmd[:300]})
    joined = " ".join(i["cmd"] for i in info)
    # granian/uvicorn workers are spawned by the venv's python; the parent chain has the reflex binary.
    ok = f"/envs/{venv}/" in joined
    if not ok:
        # walk up to the parent (reflex run) process
        for i in info:
            ppid = Path(f"/proc/{i['pid']}/stat").read_text().split()[3]
            pcmd = Path(f"/proc/{ppid}/cmdline").read_bytes().replace(b"\0", b" ").decode()
            i["parent"] = pcmd[:300]
            ok = ok or f"/envs/{venv}/" in pcmd
    assert ok, f"server on {port} is not from venv {venv}: {info}"
    return {"listeners": info, "venv": venv}


def parse_frame(data: str) -> dict:
    """Summarise one socket.io frame of the reflex event socket.

    Args:
        data: The raw frame text.

    Returns:
        A summary dict (packet type, event names, delta substates and keys).
    """
    s: dict = {"len": len(data), "head": data[:2]}
    # socket.io packets on a namespace look like `42/_event,[...]`; strip the namespace.
    if len(data) > 2 and data[2] == "/":
        comma = data.find(",")
        s["nsp"] = data[2:comma] if comma != -1 else data[2:]
        data = data[:2] + (data[comma + 1 :] if comma != -1 else "")
    try:
        if data.startswith("42"):
            name, payload = json.loads(data[2:])[:2]
            if isinstance(payload, str):
                payload = json.loads(payload)
            s["sio_event"] = name
            if isinstance(payload, dict):
                if "delta" in payload:
                    s["delta"] = {k: sorted(v.keys()) if isinstance(v, dict) else v for k, v in (payload["delta"] or {}).items()}
                    s["final"] = payload.get("final")
                    s["events"] = payload.get("events")
                if "name" in payload:
                    s["event_name"] = payload["name"]
                    s["payload_keys"] = sorted((payload.get("payload") or {}).keys())
        elif data.startswith("40"):
            body = json.loads(data[2:]) if len(data) > 2 else None
            if isinstance(body, dict):
                s["auth_keys"] = sorted(body.keys())
                txt = json.dumps(body)
                s["auth_mentions_hydrate_and_load"] = "hydrate_and_load" in txt
                for v in body.values():
                    if isinstance(v, str) and "hydrate" in v:
                        try:
                            ev = json.loads(v)
                            s["auth_event_name"] = ev.get("name") if isinstance(ev, dict) else None
                        except Exception:
                            s["auth_event_snippet"] = v[:200]
                    elif isinstance(v, dict) and "name" in v:
                        s["auth_event_name"] = v.get("name")
                    elif isinstance(v, list):
                        s["auth_event_names"] = [e.get("name") for e in v if isinstance(e, dict)]
    except Exception as e:  # noqa: BLE001
        s["parse_error"] = repr(e)
    return s


def timeline(trace: list[dict]) -> list[str]:
    """Render the in-page trace as compact, time-ordered lines.

    Args:
        trace: window.__trace entries.

    Returns:
        Human-readable lines.
    """
    lines = []
    for e in sorted(trace, key=lambda e: e.get("t", 0)):
        t = f"{e.get('t', 0):9.1f}ms"
        ev = e["ev"]
        if ev == "__reflex_set":
            lines.append(f"{t} window.__reflex ASSIGNED ({e.get('keys')} libs) at {e.get('stack', '')[:300]}")
        elif ev == "probe_render":
            lines.append(f"{t} probe render {e['label']} #{e['n']} {'HAS_REFLEX' if e['has'] else 'NO_REFLEX'} value={e['value'][:60]}")
        elif ev in ("ws_in", "ws_out"):
            p = parse_frame(e["data"])
            desc = {k: v for k, v in p.items() if k not in ("head",)}
            lines.append(f"{t} {ev} {json.dumps(desc)[:600]}")
        elif ev == "grid":
            lines.append(f"{t} grid counts (headers, cells) {json.dumps(e['counts'])}")
        else:
            lines.append(f"{t} {ev} {json.dumps({k: v for k, v in e.items() if k not in ('ev', 't')})[:200]}")
    return lines


class Runner:
    """Runs scenarios against one server."""

    def __init__(self, browser, base: str, out: Path, app: str):
        self.browser = browser
        self.base = base.rstrip("/")
        self.out = out
        self.app = app
        self.ctx = None
        self.page = None
        self.console: list[dict] = []
        self.errors: list[str] = []
        self.pw_frames: list[dict] = []
        self.t_nav = time.time()

    def new_context(self):
        if self.ctx:
            self.ctx.close()
        self.ctx = self.browser.new_context(viewport={"width": 1000, "height": 900})
        self.ctx.add_init_script(INIT_JS)
        self.page = self.ctx.new_page()
        self.page.on("console", lambda m: self.console.append({"type": m.type, "text": m.text[:500], "t": round(time.time() - self.t_nav, 3)}))
        self.page.on("pageerror", lambda e: self.errors.append(str(e)[:500]))
        self.page.on("websocket", self._on_ws)

    def _on_ws(self, ws):
        if "_event" not in ws.url:
            return
        ws.on("framereceived", lambda p: self.pw_frames.append({"dir": "in", "t": round(time.time() - self.t_nav, 3), "summary": parse_frame(p if isinstance(p, str) else "")}))
        ws.on("framesent", lambda p: self.pw_frames.append({"dir": "out", "t": round(time.time() - self.t_nav, 3), "summary": parse_frame(p if isinstance(p, str) else "")}))

    def reset_capture(self):
        self.console, self.errors, self.pw_frames = [], [], []
        self.t_nav = time.time()

    def wait_boot(self, timeout: float = 45.0, settle: float = 3.0):
        """Wait until the boot delta(s) arrived, then let things settle."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            n = self.page.evaluate("() => (window.__trace || []).filter(e => e.ev === 'ws_in' && e.data.includes('delta')).length")
            if n:
                break
            time.sleep(0.2)
        else:
            print("  WARNING: no delta frame within timeout", flush=True)
        time.sleep(settle)

    def measure(self) -> dict:
        return self.page.evaluate(MEASURE_JS, GRID_WRAPPERS)

    def snapshot(self, name: str, extra: dict | None = None) -> dict:
        m = self.measure()
        time.sleep(4)
        m_late = self.measure()
        trace = self.page.evaluate("() => window.__trace || []")
        self.page.screenshot(path=str(self.out / f"{name}.png"), full_page=True)
        frames = [dict(t=round(e["t"], 1), dir=e["ev"], **parse_frame(e["data"])) for e in trace if e["ev"] in ("ws_in", "ws_out")]
        rec = {
            "scenario": name,
            "measure": m,
            "measure_plus4s": m_late,
            "boot_frames": frames,
            "timeline": timeline(trace),
            "console": self.console,
            "pageerrors": self.errors,
            "pw_frames": self.pw_frames,
            "raw_ws": [{"t": round(e["t"], 1), "dir": e["ev"], "data": e["data"][:6000]} for e in trace if e["ev"] in ("ws_in", "ws_out")],
            **(extra or {}),
        }
        (self.out / f"{name}.json").write_text(json.dumps(rec, indent=1))
        grids = {k: (len(v["headers"]), v["cells"]) for k, v in m_late["grids"].items()}
        probes = m_late["probes"]
        print(f"[{name}] grids(headers,cells)={grids} probes={probes} counts={m_late['probeCounts']} reflexSetAt={m_late['reflexSetAt']}", flush=True)
        for f in frames:
            if f.get("delta") is not None:
                print(f"   t={f['t']} delta substates={list(f['delta'].keys())}", flush=True)
            elif f["dir"] == "ws_out" or f.get("sio_event"):
                print(f"   t={f['t']} {f['dir']} {json.dumps({k: v for k, v in f.items() if k not in ('t', 'dir', 'len', 'head')})[:200]}", flush=True)
        errs = [c for c in self.console if c["type"] in ("error", "warning")]
        if errs or self.errors:
            print(f"   console errors/warnings: {len(errs)}; pageerrors: {len(self.errors)}", flush=True)
            for c in errs[:6]:
                print(f"     {c['type']}: {c['text'][:200]}", flush=True)
            for e in self.errors[:4]:
                print(f"     pageerror: {e[:200]}", flush=True)
        return rec

    def goto(self, path: str):
        self.reset_capture()
        self.page.goto(self.base + path, wait_until="load")
        self.wait_boot()

    def reload(self):
        self.reset_capture()
        self.page.reload(wait_until="load")
        self.wait_boot()

    def click(self, sel: str, wait: float = 2.0):
        self.reset_capture()
        self.page.click(sel)
        time.sleep(wait)

    def client_nav(self, sel: str, expect_heading: str):
        self.reset_capture()
        self.page.click(sel)
        self.page.wait_for_function("(h) => document.getElementById('heading')?.textContent === h", arg=expect_heading, timeout=20000)
        time.sleep(3)


def run_entv(r: Runner, only: set[str] | None):
    def want(n):
        return not only or n in only

    if want("s1"):
        r.new_context()
        r.goto("/")
        r.snapshot("s1_full_load")
        r.reload()
        r.snapshot("s2_reload")
        r.click("#bump-other")
        r.snapshot("s3_after_unrelated_event")
        r.click("#bump-gridstate")
        r.snapshot("s4_after_same_substate_event")
        r.reload()
        r.snapshot("s5_reload_after_state_changed")
    if want("s6"):
        r.new_context()
        r.goto("/other")
        r.client_nav("#nav-index", "entv index")
        r.snapshot("s6_client_nav_from_other")
    if want("s7"):
        r.new_context()
        r.goto("/")
        r.client_nav("#nav-other", "entv other")
        r.client_nav("#nav-index", "entv index")
        r.snapshot("s7_full_load_then_nav_away_and_back")
    if want("s8"):
        r.new_context()
        r.goto("/memo")
        r.snapshot("s8_memo_full_load")
    if want("s9"):
        r.new_context()
        r.goto("/onload")
        r.snapshot("s9_onload_page_full_load")
    if want("s11"):
        # master-detail: expand row 1 of each grid and count the DETAIL grid's header cells
        r.new_context()
        r.goto("/detail")
        for wid in ("w_detail_state", "w_detail_literal"):
            r.page.locator(f"#{wid} .ag-group-contracted").first.click()
        time.sleep(2.5)
        extra = r.page.evaluate("""() => Object.fromEntries(["w_detail_state", "w_detail_literal"].map((id) => {
            const el = document.getElementById(id);
            const det = el.querySelector(".ag-details-row");
            return [id, {detail_rows: el.querySelectorAll(".ag-details-row").length,
                         detail_headers: det ? Array.from(det.querySelectorAll(".ag-header-cell")).map((e) => e.innerText.trim()) : null,
                         detail_cells: det ? det.querySelectorAll(".ag-cell").length : null}];
        }))""")
        print(f"[s11 detail] {extra}", flush=True)
        r.snapshot("s11_detail_expand", {"detail": extra})
    if want("s12"):
        r.new_context()
        r.goto("/renderer")
        badges = r.page.evaluate("() => document.querySelectorAll('#w_renderer .rt-Badge').length")
        print(f"[s12 renderer] badges={badges}", flush=True)
        r.snapshot("s12_renderer_full_load", {"badges": badges})
    if want("s13"):
        r.new_context()
        r.goto("/item/1")
        r.snapshot("s13_dynamic_route_full_load")
    if want("s10"):
        # second, independent fresh context full load (repeatability)
        r.new_context()
        r.goto("/")
        r.snapshot("s10_full_load_second_context")


def run_corev(r: Runner, only: set[str] | None):
    def want(n):
        return not only or n in only

    if want("c1"):
        r.new_context()
        r.goto("/")
        r.snapshot("c1_full_load")
        r.reload()
        r.snapshot("c2_reload")
        r.click("#bump-other")
        r.snapshot("c3_after_unrelated_event")
        r.click("#bump-untouched")
        r.snapshot("c4_after_same_substate_event")
        r.reload()
        r.snapshot("c5_reload_after_state_changed")
    if want("c6"):
        r.new_context()
        r.goto("/second")
        r.snapshot("c6a_second_full_load")
        r.client_nav("#to-index", "corev index")
        r.snapshot("c6_client_nav_from_second")
    if want("c8"):
        r.new_context()
        r.goto("/dyn")
        time.sleep(2)
        badge = r.page.evaluate("() => document.getElementById('dyn-badge')?.textContent ?? null")
        print(f"[c8 dyn] badge={badge!r}", flush=True)
        r.snapshot("c8_dynamic_component_full_load", {"dyn_badge": badge})
    if want("c7"):
        r.new_context()
        r.goto("/")
        r.snapshot("c7_full_load_second_context")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", required=True, choices=["entv", "corev"])
    ap.add_argument("--url", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--server-venv", required=True)
    ap.add_argument("--only", default="")
    ap.add_argument("--backend-port", type=int, default=0, help="dev mode: port whose listener must run from --server-venv")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    port = int(a.url.rsplit(":", 1)[1].split("/")[0])
    info = server_check(a.backend_port or port, a.server_venv)
    (out / "server_check.json").write_text(json.dumps(info, indent=1))
    print("server check ok:", info["listeners"][0]["cmd"][:160], flush=True)
    only = set(a.only.split(",")) if a.only else None
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        r = Runner(browser, a.url, out, a.app)
        try:
            (run_entv if a.app == "entv" else run_corev)(r, only)
        finally:
            if r.ctx:
                r.ctx.close()
            browser.close()


if __name__ == "__main__":
    main()
