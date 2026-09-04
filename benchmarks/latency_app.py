"""Benchmark app factory for measuring Reflex latency."""


def BenchApp():
    import asyncio

    import reflex as rx

    ROWS = 100

    class State(rx.State):
        counter: int = 0
        items: list[dict[str, str]] = [
            {"id": str(i), "name": f"Item {i}", "status": "ok" if i % 3 else "warn"}
            for i in range(ROWS)
        ]
        loaded_at: str = ""
        text: str = ""

        @rx.var
        def total(self) -> int:
            return len(self.items) + self.counter

        @rx.event
        def inc(self):
            self.counter += 1

        @rx.event
        async def load_slow(self):
            await asyncio.sleep(0.02)
            self.loaded_at = f"slow{self.counter}"

        @rx.event
        def load_fast(self):
            self.loaded_at = f"fast{self.counter}"

        @rx.event
        def set_text(self, value: str):
            self.text = value

    def nav():
        return rx.hstack(
            rx.link("index", href="/", id="nav-index"),
            rx.link("table", href="/table", id="nav-table"),
            rx.link("loaded", href="/loaded", id="nav-loaded"),
            rx.link("loaded_fast", href="/loaded_fast", id="nav-loaded_fast"),
            rx.link("static", href="/static", id="nav-static"),
            rx.link("form", href="/form", id="nav-form"),
        )

    def hydrated_marker():
        return rx.cond(
            rx.State.is_hydrated,
            rx.text("hydrated", id="hydrated"),
            rx.text("loading", id="loading"),
        )

    def counter_block():
        return rx.hstack(
            rx.button("inc", id="inc", on_click=State.inc),
            rx.text(State.counter, id="counter"),
            rx.text(State.total, id="total"),
        )

    def shell(name, *children):
        return rx.vstack(
            nav(),
            hydrated_marker(),
            rx.el.div(id=f"page-{name}"),
            counter_block(),
            *children,
        )

    def index():
        return shell("index", rx.heading("Index"))

    def table():
        return shell(
            "table",
            rx.table.root(
                rx.table.body(
                    rx.foreach(
                        State.items,
                        lambda item: rx.table.row(
                            rx.table.cell(item["id"]),
                            rx.table.cell(item["name"]),
                            rx.table.cell(rx.badge(item["status"])),
                        ),
                    )
                )
            ),
        )

    def loaded():
        return shell("loaded", rx.text(State.loaded_at, id="loaded_at"))

    def loaded_fast():
        return shell("loaded_fast", rx.text(State.loaded_at, id="loaded_at"))

    def static():
        return rx.vstack(nav(), rx.el.div(id="page-static"), rx.heading("Static"))

    def form():
        return shell(
            "form",
            rx.input(value=State.text, on_change=State.set_text, id="text"),
            rx.text(State.text, id="text_out"),
        )

    app = rx.App()
    app.add_page(index, route="/")
    app.add_page(table, route="/table")
    app.add_page(loaded, route="/loaded", on_load=State.load_slow)
    app.add_page(loaded_fast, route="/loaded_fast", on_load=State.load_fast)
    app.add_page(static, route="/static")
    app.add_page(form, route="/form")
