"""Large-state page: delta granularity and re-render cost when one var in a busy substate changes."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent))
from latency_browser import INIT_SCRIPT, ServerTimers, WsLog, agg, launch_chromium

from reflex.testing import AppHarnessProd

ROWS = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
N = 15


def BigApp():
    import reflex as rx

    ROWS = int("__ROWS__")  # replaced with the row count before the source is written

    class State(rx.State):
        counter: int = 0
        rows: list[dict[str, int | str]] = [
            {"id": i, "name": f"row {i}", "value": i % 97} for i in range(ROWS)
        ]
        other: int = 0

        @rx.event
        def inc(self):
            self.counter += 1

        @rx.event
        def bump_one(self):
            self.rows[0]["value"] = int(self.rows[0]["value"]) + 1

        @rx.event
        def bump_other(self):
            self.other += 1

    class Isolated(rx.State):
        n: int = 0

        @rx.event
        def inc(self):
            self.n += 1

    def row(item):
        return rx.table.row(
            rx.table.cell(item["id"]),
            rx.table.cell(item["name"]),
            rx.table.cell(item["value"], class_name="val"),
        )

    def big():
        return rx.vstack(
            rx.hstack(
                rx.button("inc", id="inc", on_click=State.inc),
                rx.text(State.counter, id="counter"),
                rx.button("bump_one", id="bump_one", on_click=State.bump_one),
                rx.button("bump_other", id="bump_other", on_click=State.bump_other),
                rx.text(State.other, id="other"),
                rx.button("iso", id="iso", on_click=Isolated.inc),
                rx.text(Isolated.n, id="iso_n"),
            ),
            rx.el.div(id="page-big"),
            rx.table.root(rx.table.body(rx.foreach(State.rows, row)), id="tbl"),
        )

    app = rx.App()
    app.add_page(big, route="/")


def run_click(page, wslog, button, watch_js, n=N):
    out = []
    for _ in range(n):
        before = page.evaluate(watch_js)
        page.evaluate("window.__marks.length = 0")
        f0 = len(wslog.frames)
        page.click(f"#{button}")
        page.wait_for_function(f"({watch_js}) !== {json.dumps(before)}")
        marks = page.evaluate("window.__marks")
        click_t = next(m["t"] for m in marks if m["name"] == "click")
        done_t = page.evaluate("performance.now()")
        frames = wslog.frames[f0:]
        sent = [t for d, t, _p in frames if d == "sent"]
        recv = [t for d, t, _p in frames if d == "recv"]
        out.append({
            "click_to_dom_update": round(done_t - click_t, 1),
            "ws_sent_to_recv(cdp)": round((recv[0] - sent[0]) * 1000, 1)
            if sent and recv
            else None,
            "delta_bytes": len(frames[[d for d, _t, _p in frames].index("recv")][2])
            if recv
            else None,
        })
        page.wait_for_timeout(30)
    return agg(out)


def main():
    import inspect
    import textwrap

    lines = inspect.getsource(BigApp).splitlines()[1:]
    module_src = textwrap.dedent("\n".join(lines)).replace("__ROWS__", str(ROWS))
    root = Path(__file__).parent / f"app_big_{ROWS}"
    root.mkdir(exist_ok=True)
    report: dict[str, Any] = {"rows": ROWS}
    with AppHarnessProd.create(
        root=root, app_source=module_src, app_name="bigapp"
    ) as harness:
        timers = ServerTimers(harness)
        with sync_playwright() as pw:
            browser = launch_chromium(pw)
            context = browser.new_context()
            context.add_init_script(INIT_SCRIPT)
            page = context.new_page()
            wslog = WsLog()
            wslog.attach(page, context)
            loads = []
            for _ in range(3):
                f0 = len(wslog.frames)
                assert harness.frontend_url is not None
                page.goto(harness.frontend_url)
                page.wait_for_function(
                    f"document.querySelectorAll('#tbl tr').length >= {ROWS}",
                    timeout=60000,
                )
                nav = page.evaluate(
                    "performance.getEntriesByType('navigation')[0].toJSON()"
                )
                t_rows = page.evaluate("performance.now()")
                frames = wslog.frames[f0:]
                hyd = next(
                    (len(p) for d, _t, p in frames if d == "recv" and '"delta"' in p),
                    None,
                )
                loads.append({
                    "domContentLoaded": round(nav["domContentLoadedEventEnd"], 1),
                    "rows_rendered_at": round(t_rows, 1),
                    "hydrate_bytes": hyd,
                })
            report["cold_load"] = agg(loads)
            report["inc counter (same substate as big list)"] = run_click(
                page, wslog, "inc", "document.querySelector('#counter').textContent"
            )
            report["bump_other (same substate, unrelated var)"] = run_click(
                page,
                wslog,
                "bump_other",
                "document.querySelector('#other').textContent",
            )
            report["bump_one (mutate 1 of N rows)"] = run_click(
                page,
                wslog,
                "bump_one",
                "document.querySelector('#tbl .val').textContent",
            )
            report["iso (different substate)"] = run_click(
                page, wslog, "iso", "document.querySelector('#iso_n').textContent"
            )
            browser.close()
        report["server_timers"] = timers.report()
    (Path(__file__).parent / f"report_big_{ROWS}.json").write_text(
        json.dumps(report, indent=2)
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
