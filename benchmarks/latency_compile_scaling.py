"""Time `import reflex`, app import and App._compile for apps of increasing page count."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

os.environ["REFLEX_TELEMETRY_ENABLED"] = "false"
HERE = Path(__file__).parent
APP_DIR = HERE / "app_compile"
APP_DIR.mkdir(exist_ok=True)
(APP_DIR / "rxconfig.py").write_text(
    'import reflex as rx\n\nconfig = rx.Config(app_name="compileapp")\n'
)
os.chdir(APP_DIR)

t0 = time.perf_counter()
import reflex as rx  # noqa: E402

t_import = time.perf_counter() - t0


def build_app(n_pages: int, rows: int = 30):
    class State(rx.State):
        counter: int = 0
        items: list[dict[str, str]] = [
            {"id": str(i), "name": f"n{i}"} for i in range(rows)
        ]

        @rx.event
        def inc(self):
            self.counter += 1

    def nav():
        return rx.hstack(*[
            rx.link(f"p{i}", href=f"/p{i}") for i in range(min(n_pages, 20))
        ])

    def make_page(i):
        def page():
            return rx.vstack(
                nav(),
                rx.heading(f"Page {i}"),
                rx.button("inc", on_click=State.inc),
                rx.text(State.counter),
                rx.card(rx.text("card"), rx.badge("b"), rx.input(placeholder="x")),
                rx.table.root(
                    rx.table.body(
                        rx.foreach(
                            State.items,
                            lambda item: rx.table.row(
                                rx.table.cell(item["id"]), rx.table.cell(item["name"])
                            ),
                        )
                    )
                ),
                *[
                    rx.hstack(rx.text(f"row {j}"), rx.switch(), rx.select(["a", "b"]))
                    for j in range(10)
                ],
            )

        page.__name__ = f"page{i}"
        return page

    from reflex_base.registry import RegistrationContext

    RegistrationContext.set(RegistrationContext.ensure_context().fork())
    app = rx.App()
    for i in range(n_pages):
        app.add_page(make_page(i), route="/" if i == 0 else f"/p{i}")
    return app


out = {"import_reflex_s": round(t_import, 2), "compiles": []}
for n in [1, 5, 20, 50]:
    app = build_app(n)
    t0 = time.perf_counter()
    app._compile(dry_run=True, use_rich=False)
    dt = time.perf_counter() - t0
    out["compiles"].append({
        "pages": n,
        "compile_s": round(dt, 2),
        "per_page_ms": round(dt / n * 1000),
    })
    print(out["compiles"][-1], flush=True)
(HERE / "report_compile_scaling.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out))
