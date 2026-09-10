"""Drive the hmr_app under `reflex run` and edit its Python source while the page is open.

Run with the driver venv (playwright), never with an app venv:

    NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
      $SB/envs/driver/bin/python hmr_driver.py \
        --url http://localhost:3100 --backend-port 8100 \
        --app-file $SB/apps/hmr_runtime/hmr_app/hmr_app/hmr_app.py \
        --out $SB/apps/hmr_runtime/logs/hmr_new --label new

Per edit it records: page errors, console errors/warnings, vite HMR frames (update / full-reload),
socket.io websocket opens (reconnects), refetches of utils/state.js, whether DOM nodes survived
(a JS property stamped on elements before the edit), counter value vs clicks issued during the
update window, rx.set_focus after the edit, client_state value, ComponentState value, todos.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright

CHROMIUM = "/opt/pw-browsers/chromium"
BENIGN = [
    re.compile(r"Hey developer.*HydrateFallback|reactrouter\.com/start/framework/route-module"),
    re.compile(r"\[vite\] (connecting|connected)"),
    re.compile(r"Download the React DevTools"),
]


def now() -> float:
    return time.time()


class Recorder:
    def __init__(self, page, backend_port: int, log):
        self.page = page
        self.backend_port = backend_port
        self.log = log
        self.console: list[tuple[float, str, str]] = []
        self.errors: list[tuple[float, str]] = []
        self.failed: list[tuple[float, str, str]] = []
        self.bad_responses: list[tuple[float, int, str]] = []
        self.ws: list[dict] = []
        self.vite_frames: list[tuple[float, dict]] = []
        self.state_js_requests: list[tuple[float, str]] = []
        self.context_requests: list[tuple[float, str]] = []
        page.on("console", self._on_console)
        page.on("pageerror", lambda e: self.errors.append((now(), str(e))))
        page.on("requestfailed", lambda r: self.failed.append((now(), r.url, str(r.failure))))
        page.on("response", self._on_response)
        page.on("request", self._on_request)
        page.on("websocket", self._on_ws)

    def _on_console(self, msg):
        text = msg.text
        self.console.append((now(), msg.type, text))
        if "ERR_CONNECTION_REFUSED" in text:
            return  # expected while the backend worker restarts; counted separately
        if msg.type in ("error", "warning") and not any(b.search(text) for b in BENIGN):
            self.log(f"  [console.{msg.type}] {text[:300]}")

    def _on_response(self, r):
        if r.status >= 400:
            self.bad_responses.append((now(), r.status, r.url))

    def _on_request(self, r):
        url = r.url
        if "/utils/state.js" in url:
            self.state_js_requests.append((now(), url))
        if re.search(r"/utils/context\.jsx?(\?|$)", url):
            self.context_requests.append((now(), url))

    def _on_ws(self, ws):
        url = ws.url
        rec = {"t": now(), "url": url, "closed": None, "kind": None, "frames": 0, "error": None}
        if f":{self.backend_port}/" in url or "/_event" in url:
            rec["kind"] = "socketio"
            ws.on("framereceived", lambda payload: rec.__setitem__("frames", rec["frames"] + 1))
            ws.on("socketerror", lambda err: rec.__setitem__("error", str(err)[:120]))
        else:
            rec["kind"] = "vite"
            ws.on("framereceived", lambda payload: self._on_vite_frame(payload))
        self.ws.append(rec)
        ws.on("close", lambda: rec.__setitem__("closed", now()))
        if rec["kind"] == "vite":
            self.log(f"  [ws open] {rec['kind']} {url[:120]}")

    def _on_vite_frame(self, payload):
        try:
            data = json.loads(payload)
        except Exception:
            data = {"raw": str(payload)[:200]}
        if data.get("type") in ("ping", "pong"):
            return
        self.vite_frames.append((now(), data))
        if data.get("type") == "update":
            paths = [u.get("path") for u in data.get("updates", [])]
            self.log(f"  [vite] update {paths}")
        else:
            self.log(f"  [vite] {json.dumps(data)[:200]}")

    def since(self, t0: float):
        sio = [w for w in self.ws if w["kind"] == "socketio" and w["t"] >= t0]
        sio_ok = [w for w in sio if w["frames"] > 0]
        return {
            "page_errors": [e for ts, e in self.errors if ts >= t0],
            "console_errors": [
                f"{k}: {t}"
                for ts, k, t in self.console
                if ts >= t0 and k in ("error", "warning") and "ERR_CONNECTION_REFUSED" not in t and not any(b.search(t) for b in BENIGN)
            ],
            "console_all": [f"{k}: {t[:200]}" for ts, k, t in self.console if ts >= t0],
            "conn_refused_console_errors": sum(1 for ts, k, t in self.console if ts >= t0 and "ERR_CONNECTION_REFUSED" in t),
            "socket_disconnect_logs": sum(1 for ts, k, t in self.console if ts >= t0 and "Socket is disconnected" in t),
            "ws_closed_before_established": sum(1 for ts, k, t in self.console if ts >= t0 and "closed before the connection is established" in t),
            "addEvents_before_provider": sum(1 for ts, k, t in self.console if ts >= t0 and "addEvents called before EventLoopProvider" in t),
            "failed_requests": [f"{u} {f}" for ts, u, f in self.failed if ts >= t0 and "_event" not in u],
            "bad_responses": [f"{s} {u}" for ts, s, u in self.bad_responses if ts >= t0],
            "socketio_attempts": len(sio),
            "socketio_successful_connections": len(sio_ok),
            "socketio_first_success_after_s": round(sio_ok[0]["t"] - t0, 2) if sio_ok else None,
            "vite_opens": sum(1 for w in self.ws if w["kind"] == "vite" and w["t"] >= t0),
            "vite_first_frame_after_s": round(min((ts for ts, d in self.vite_frames if ts >= t0), default=t0) - t0, 2),
            "vite_frames": [
                {"type": d.get("type"), "paths": [u.get("path") for u in d.get("updates", [])] if d.get("type") == "update" else None}
                for ts, d in self.vite_frames
                if ts >= t0
            ],
            "state_js_refetches": sum(1 for ts, u in self.state_js_requests if ts >= t0),
            "context_fetches": [u.split("/", 3)[-1] for ts, u in self.context_requests if ts >= t0],
        }


class Driver:
    def __init__(self, args):
        self.args = args
        self.out = Path(args.out)
        self.out.mkdir(parents=True, exist_ok=True)
        self.app_file = Path(args.app_file)
        self.report: dict = {"label": args.label, "url": args.url, "steps": [], "start": now()}
        self.logf = open(self.out / "driver.log", "w")
        self.expected_count = 0

    def log(self, msg: str):
        line = f"{time.strftime('%H:%M:%S')} {msg}"
        print(line, flush=True)
        self.logf.write(line + "\n")
        self.logf.flush()

    def edit(self, old: str, new: str, count: int = 1):
        src = self.app_file.read_text()
        assert src.count(old) == count, f"expected {count} occurrence(s) of {old!r}, found {src.count(old)}"
        self.app_file.write_text(src.replace(old, new))
        self.log(f"EDIT applied: {old[:60]!r} -> {new[:60]!r}")

    async def text_of(self, sel: str) -> str | None:
        try:
            el = await self.page.query_selector(sel)
            if el is None:
                return None
            return (await el.inner_text()).strip()
        except Exception as e:  # noqa: BLE001
            return f"<err {type(e).__name__}>"

    async def wait_for(self, pred, timeout: float, what: str):
        t0 = now()
        while now() - t0 < timeout:
            try:
                if await pred():
                    return True
            except Exception:  # noqa: BLE001
                pass
            await asyncio.sleep(0.15)
        self.log(f"  TIMEOUT waiting for {what}")
        return False

    async def wait_text(self, sel: str, expected: str, timeout: float = 40):
        async def pred():
            return (await self.text_of(sel)) == expected

        ok = await self.wait_for(pred, timeout, f"{sel} == {expected!r}")
        actual = await self.text_of(sel)
        return ok, actual

    async def snapshot(self) -> dict:
        p = self.page
        focus = await p.evaluate("document.activeElement && document.activeElement.id")
        marks = await p.evaluate(
            "(() => { const out = {}; for (const id of ['heading','memo-count','cs-text','todo-list']) { const el = document.getElementById(id); out[id] = el ? (el.__rx_mark || null) : 'MISSING'; } return out; })()"
        )
        todos = await p.evaluate("Array.from(document.querySelectorAll('.todo-item')).map(e => e.textContent)")
        return {
            "heading": await self.text_of("#heading"),
            "memo_count": await self.text_of("#memo-count"),
            "cond": await self.text_of("#cond-big") or await self.text_of("#cond-small"),
            "toggle": await self.text_of("#toggle-btn"),
            "cs_text": await self.text_of("#cs-text"),
            "todos": todos,
            "bg_ticks": await self.text_of("#bg-ticks"),
            "bg_status": await self.text_of("#bg-status"),
            "extra": await self.text_of("#extra-text"),
            "memo_class": await p.evaluate("(document.getElementById('memo-count')||{}).className || null"),
            "scratch": await p.evaluate("(document.getElementById('scratch')||{}).value ?? null"),
            "active_element": focus,
            "marks": marks,
        }

    async def stamp_marks(self):
        await self.page.evaluate(
            "(() => { for (const id of ['heading','memo-count','cs-text','todo-list']) { const el = document.getElementById(id); if (el) el.__rx_mark = 'stamped'; } })()"
        )

    async def check_focus(self) -> dict:
        p = self.page
        await p.click("#heading")  # move focus away
        await p.evaluate("document.activeElement && document.activeElement.blur()")
        before = await p.evaluate("document.activeElement && document.activeElement.id")
        await p.click("#focus-btn")
        ok = await self.wait_for(
            lambda: p.evaluate("document.activeElement && document.activeElement.id === 'todo_input'"), 8, "focus on todo_input"
        )
        after = await p.evaluate("document.activeElement && document.activeElement.id")
        return {"before": before, "after": after, "ok": ok}

    async def click_burst(self, n: int, interval: float, sel: str = "#inc-btn") -> int:
        done = 0
        for _ in range(n):
            try:
                await self.page.click(sel, timeout=3000)
                done += 1
            except Exception as e:  # noqa: BLE001
                self.log(f"  click failed: {type(e).__name__}: {str(e)[:120]}")
            await asyncio.sleep(interval)
        return done

    async def run_step(self, name: str, apply_edit, settle, during=None, hold_context: bool = False):
        rec = self.rec
        self.log(f"=== STEP {name} (hold_context={hold_context})")
        await self.stamp_marks()
        before = await self.snapshot()
        t0 = now()
        hold_events = []
        if hold_context:

            async def hold(route):
                hold_events.append(("hold", now(), route.request.url))
                await asyncio.sleep(self.args.hold_seconds)
                hold_events.append(("release", now(), route.request.url))
                await route.continue_()

            await self.page.route(re.compile(r".*/utils/context\.jsx?(\?.*)?$"), hold)
        c0 = self.parse_count(before["memo_count"])
        apply_edit()
        clicks = 0
        if during is not None:
            clicks = await during()
        settled, settle_info = await settle()
        # give the browser a moment for straggler frames / reconnects
        await asyncio.sleep(1.5)
        if hold_context:
            await self.page.unroute(re.compile(r".*/utils/context\.jsx?(\?.*)?$"))
        # Expected counter after the edit: pre-edit count + clicks issued during the window. If the
        # state schema changed (default/var edit) the disk state is discarded (StateSchemaMismatchError)
        # and the count restarts from 0; clicks that reached the old worker before it stopped are lost
        # with the old state, so allow up to 2 such clicks.
        label = (await self.text_of("#memo-count") or "").split(":")[0]
        count_ok, count_actual = await self.wait_text("#memo-count", f"{label}: {c0 + clicks}", 20)
        state_reset = False
        if not count_ok:
            c_now = self.parse_count(count_actual)
            if c_now is not None and clicks - 2 <= c_now <= clicks:
                state_reset = True
                count_ok = True
                self.log(f"  state reset detected (schema change): count {c0} -> {c_now} with {clicks} clicks during window")
        self.expected_count = self.parse_count(await self.text_of("#memo-count")) or 0
        focus = await self.check_focus()
        # click once more after the update to confirm events flow post-update
        await self.page.click("#inc-btn")
        self.expected_count += 1
        post_ok, post_actual = await self.wait_text("#memo-count", f"{label}: {self.expected_count}", 15)
        after = await self.snapshot()
        compiled_heading = None
        if self.args.web_dir:
            try:
                m = re.search(r"HMR Runtime App[^\"<]*", (Path(self.args.web_dir) / "app/routes/_index.jsx").read_text())
                compiled_heading = m.group(0) if m else None
            except OSError as e:
                compiled_heading = f"<{e}>"
        shot = self.out / f"{name}.png"
        await self.page.screenshot(path=str(shot), full_page=False)
        events = rec.since(t0)
        step = {
            "name": name,
            "hold_context": hold_context,
            "t_edit": t0,
            "settled": settled,
            "settle_info": settle_info,
            "settle_seconds": round(now() - t0, 2),
            "clicks_during_window": clicks,
            "count_before_edit": c0,
            "count_expected": c0 + clicks,
            "count_ok_after_window": count_ok,
            "state_reset_detected": state_reset,
            "count_actual_after_window": count_actual,
            "compiled_index_heading": compiled_heading,
            "source_heading": (re.search(r'rx\.heading\("([^"]+)", id="heading"\)', self.app_file.read_text()) or [None, None])[1],
            "post_update_click_ok": post_ok,
            "post_update_count": post_actual,
            "focus_after": focus,
            "before": before,
            "after": after,
            "marks_survived": {k: v for k, v in after["marks"].items()},
            "events": events,
            "hold_events": hold_events,
            "screenshot": str(shot),
        }
        self.report["steps"].append(step)
        verdict = "OK" if (settled and count_ok and post_ok and focus["ok"] and not events["page_errors"]) else "PROBLEM"
        step["verdict"] = verdict
        self.log(
            f"  -> {verdict}: settled={settled} in {step['settle_seconds']}s, clicks={clicks}, count {c0}->{count_actual} ok={count_ok} reset={state_reset}, "
            f"post_click_ok={post_ok}, focus_ok={focus['ok']}, sio_attempts={events['socketio_attempts']} sio_ok={events['socketio_successful_connections']} "
            f"(first ok +{events['socketio_first_success_after_s']}s), vite_frames={[f['type'] for f in events['vite_frames']]} first +{events['vite_first_frame_after_s']}s, "
            f"state_js_refetch={events['state_js_refetches']}, page_errors={events['page_errors']}, console_errors={events['console_errors'][:3]}, "
            f"marks={after['marks']}, cs={after['cs_text']!r}, scratch={after['scratch']!r}, toggle={after['toggle']!r}, compiled_heading={compiled_heading!r}, source_heading={step['source_heading']!r}"
        )
        return step

    @staticmethod
    def parse_count(text: str | None) -> int | None:
        m = re.search(r": (-?\d+)$", text or "")
        return int(m.group(1)) if m else None

    async def settle_backend_restart(self, t0: float, timeout: float = 45):
        """Wait until socket.io has (re)connected after the backend restart triggered by an edit."""
        rec = self.rec

        async def pred():
            return any(w["kind"] == "socketio" and w["t"] >= t0 for w in rec.ws) and (now() - t0) > 1.0

        ok = await self.wait_for(pred, timeout, "socket.io reconnect after edit")
        # then wait until the newest socket.io ws is not closed (stable)
        await asyncio.sleep(1.0)
        return ok

    async def run(self):
        a = self.args
        async with async_playwright() as p:
            browser = await p.chromium.launch(executable_path=CHROMIUM)
            context = await browser.new_context(viewport={"width": 1200, "height": 900})
            self.page = page = await context.new_page()
            self.rec = rec = Recorder(page, a.backend_port, self.log)
            t_load = now()
            await page.goto(a.url + "/", wait_until="networkidle")
            ok, actual = await self.wait_text("#memo-count", "Counter: 0", 60)
            self.log(f"initial load: memo-count={actual!r} ok={ok}")
            self.report["initial_load"] = {"ok": ok, "memo_count": actual, "events": rec.since(t_load)}
            await page.screenshot(path=str(self.out / "00_initial.png"))
            if not ok:
                self.log("initial state not as expected (state may persist from a previous run); resetting expected count")
                m = re.search(r": (-?\d+)$", actual or "")
                self.expected_count = int(m.group(1)) if m else 0

            # Baseline interactions before any edit.
            for _ in range(3):
                await page.click("#inc-btn")
            self.expected_count += 3
            ok, actual = await self.wait_text("#memo-count", f"Counter: {self.expected_count}")
            self.log(f"3 clicks: {actual!r} ok={ok}")
            await page.click("#cs-btn")
            ok_cs, cs = await self.wait_text("#cs-text", "client: cs-changed")
            await page.click("#toggle-btn")
            ok_tg, tg = await self.wait_text("#toggle-btn", "Toggle: ON")
            await page.fill("#todo_input", "buy milk")
            await page.click("#add-btn")
            await self.wait_for(lambda: page.evaluate("document.querySelectorAll('.todo-item').length >= 2"), 10, "todo added")
            try:
                await page.fill("#scratch", "keep-me")
            except Exception as e:  # noqa: BLE001
                self.log(f"no #scratch input: {e}")
            focus0 = await self.check_focus()
            await page.click("#bg-start")
            await self.wait_for(lambda: page.evaluate("document.getElementById('bg-ticks').textContent.trim() !== 'ticks: 0'"), 10, "bg ticks")
            pre = await self.snapshot()
            self.report["pre_edit"] = {"snapshot": pre, "cs_ok": ok_cs, "toggle_ok": ok_tg, "focus": focus0, "events": rec.since(t_load)}
            self.log(f"pre-edit snapshot: {json.dumps(pre)[:400]}")
            await page.screenshot(path=str(self.out / "01_pre_edit.png"))

            steps = a.steps.split(",")

            # 1. change rendered text (page module only)
            if "text" in steps:
                await self.run_step(
                    "text",
                    lambda: self.edit('rx.heading("HMR Runtime App", id="heading")', 'rx.heading("HMR Runtime App v2", id="heading")'),
                    lambda: self.wait_text("#heading", "HMR Runtime App v2"),
                    during=lambda: self.click_burst(12, 0.25),
                )
                bg = await self.snapshot()
                self.log(f"  bg after text edit: ticks={bg['bg_ticks']} status={bg['bg_status']}")
                await asyncio.sleep(1.0)
                bg2 = await self.snapshot()
                self.report["bg_after_text_edit"] = {"immediately": bg, "1s_later": bg2}
                self.log(f"  bg 1s later: ticks={bg2['bg_ticks']} status={bg2['bg_status']}")

            # 2. change a state default (context.jsx changes)
            if "default" in steps:
                t_mark = now()
                await self.run_step(
                    "default",
                    lambda: self.edit('label: str = "Counter"  # EDIT_DEFAULT', 'label: str = "Compteur"  # EDIT_DEFAULT'),
                    lambda: self._settle_restart_then(t_mark),
                    during=lambda: self.click_burst(8, 0.3),
                )
                self.log(f"  label after default edit: {await self.text_of('#memo-count')!r} (backend state persisted on disk keeps old value?)")

            # 3. add a new var and render it
            if "newvar" in steps:
                def edit_newvar():
                    self.edit("    # EDIT_NEWVAR", "    extra: int = 7\n    # EDIT_NEWVAR")
                    self.edit(
                        "        counter_display(count=State.count, label=State.label),",
                        '        counter_display(count=State.count, label=State.label),\n        rx.text("extra: ", State.extra, id="extra-text"),',
                    )

                await self.run_step(
                    "newvar",
                    edit_newvar,
                    lambda: self.wait_text("#extra-text", "extra: 7"),
                    during=lambda: self.click_burst(8, 0.3),
                )

            # 4. add a new event handler and a button for it
            if "handler" in steps:
                def edit_handler():
                    self.edit(
                        "    # EDIT_HANDLER",
                        "    @rx.event\n    def add_ten(self):\n        self.count += 10\n\n    # EDIT_HANDLER",
                    )
                    self.edit(
                        '            rx.button("+", on_click=State.increment, id="inc-btn"),',
                        '            rx.button("+", on_click=State.increment, id="inc-btn"),\n            rx.button("+10", on_click=State.add_ten, id="add-ten-btn"),',
                    )

                async def settle_handler():
                    ok = await self.wait_for(lambda: page.evaluate("!!document.getElementById('add-ten-btn')"), 40, "add-ten-btn present")
                    return ok, "add-ten-btn present" if ok else "add-ten-btn missing"

                step = await self.run_step("handler", edit_handler, settle_handler, during=lambda: self.click_burst(8, 0.3))
                if step["settled"]:
                    await page.click("#add-ten-btn")
                    self.expected_count += 10
                    label = (await self.text_of("#memo-count") or "").split(":")[0]
                    ok, actual = await self.wait_text("#memo-count", f"{label}: {self.expected_count}")
                    step["new_handler_click_ok"] = ok
                    step["new_handler_count"] = actual
                    self.log(f"  new handler +10 click: ok={ok} ({actual})")

            # 5. change component props (memo component)
            if "props" in steps:
                async def settle_props():
                    ok = await self.wait_for(
                        lambda: page.evaluate("(document.getElementById('memo-count')||{className:''}).className.includes('rt-r-size-8')"), 40, "size-8 class"
                    )
                    return ok, await page.evaluate("(document.getElementById('memo-count')||{}).className")

                await self.run_step(
                    "props",
                    lambda: self.edit('id="memo-count", size="6")  # EDIT_PROPS', 'id="memo-count", size="8", color_scheme="red")  # EDIT_PROPS'),
                    settle_props,
                    during=lambda: self.click_burst(8, 0.3),
                )

            # 6. two edits in quick succession (gap configurable), then again with a longer gap
            if "double" in steps:
                def edit_double():
                    self.edit('"HMR Runtime App v2"', '"HMR Runtime App v3"')

                async def during_double():
                    await asyncio.sleep(a.double_gap)
                    self.edit('"HMR Runtime App v3"', '"HMR Runtime App v4"')
                    return await self.click_burst(10, 0.3)

                await self.run_step("double", edit_double, lambda: self.wait_text("#heading", "HMR Runtime App v4", 30), during=during_double)
                # make sure the source is at v4 regardless (it is; only the compile may lag)

            if "double_long" in steps:
                def edit_double2():
                    self.edit('"HMR Runtime App v4"', '"HMR Runtime App v5"')

                async def during_double2():
                    await asyncio.sleep(a.double_gap_long)
                    self.edit('"HMR Runtime App v5"', '"HMR Runtime App v6"')
                    return await self.click_burst(10, 0.3)

                await self.run_step("double_long", edit_double2, lambda: self.wait_text("#heading", "HMR Runtime App v6", 30), during=during_double2)

            # 7. hold context module requests while a state-default edit lands; navigate during the hold
            if "hold" in steps:
                t_mark2 = now()

                async def during_hold():
                    n = await self.click_burst(4, 0.2)
                    try:
                        await page.click("#nav-page3", timeout=5000)
                        await self.wait_for(lambda: page.evaluate("!!document.getElementById('page3-heading')"), 15, "page3")
                        self.log(f"  navigated to page3: count text={await self.text_of('#page3-count')!r}")
                        await page.click("#nav-home", timeout=5000)
                        await self.wait_for(lambda: page.evaluate("!!document.getElementById('inc-btn')"), 15, "home")
                    except Exception as e:  # noqa: BLE001
                        self.log(f"  navigation during hold failed: {e}")
                    n += await self.click_burst(4, 0.2)
                    return n

                await self.run_step(
                    "hold",
                    lambda: self.edit('label: str = "Compteur"  # EDIT_DEFAULT', 'label: str = "Zaehler"  # EDIT_DEFAULT'),
                    lambda: self._settle_restart_then(t_mark2),
                    during=during_hold,
                    hold_context=True,
                )

            # Navigation sanity across pages at the end.
            nav = {}
            for route, sel in [("/about", "#about-heading"), ("/page2", "#page2-heading"), ("/long", "#long-end"), ("/", "#heading")]:
                t_nav = now()
                await page.click(f"#nav-{'home' if route == '/' else route.strip('/')}")
                ok = await self.wait_for(lambda s=sel: page.evaluate(f"!!document.querySelector('{s}')"), 30, route)
                nav[route] = {"ok": ok, "ms": round((now() - t_nav) * 1000)}
            self.report["nav_after_edits"] = nav
            self.log(f"nav after edits: {nav}")
            await page.screenshot(path=str(self.out / "99_final.png"))
            self.report["final_snapshot"] = await self.snapshot()
            self.report["all_events"] = rec.since(0)
            self.report["ws"] = rec.ws
            self.report["end"] = now()
            await browser.close()
        (self.out / "report.json").write_text(json.dumps(self.report, indent=2, default=str))
        self.log(f"report written to {self.out / 'report.json'}")

    async def _settle_restart_then(self, t0):
        ok = await self.settle_backend_restart(t0)
        # context.jsx update frame should have arrived too
        frames = [d for ts, d in self.rec.vite_frames if ts >= t0]
        return ok, {"vite_frames": [d.get("type") for d in frames]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--backend-port", type=int, required=True)
    ap.add_argument("--app-file", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", default="run")
    ap.add_argument("--steps", default="text,default,newvar,handler,props,double,double_long,hold")
    ap.add_argument("--hold-seconds", type=float, default=3.0)
    ap.add_argument("--double-gap", type=float, default=0.5)
    ap.add_argument("--double-gap-long", type=float, default=2.5)
    ap.add_argument("--web-dir", default=None, help="path to the app's .web dir, to compare compiled output with source")
    args = ap.parse_args()
    asyncio.run(Driver(args).run())


if __name__ == "__main__":
    sys.exit(main())
