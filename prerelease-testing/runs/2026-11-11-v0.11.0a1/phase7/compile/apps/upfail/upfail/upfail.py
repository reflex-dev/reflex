"""FINDING-044 browser repro: upload handlers that fail before / after their first update."""

import asyncio

import reflex as rx


class S(rx.State):
    n: int = 0
    prog: list[str] = []
    done: list[str] = []

    @rx.event
    async def fail_now(self, files: list[rx.UploadFile]):
        for f in files:
            await f.read()
        raise ValueError("boom before any update")

    @rx.event
    async def fail_later(self, files: list[rx.UploadFile]):
        for f in files:
            await f.read()
        self.n += 1
        yield
        await asyncio.sleep(0.2)
        raise ValueError("boom after an update")

    @rx.event
    async def ok(self, files: list[rx.UploadFile]):
        for f in files:
            await f.read()
        self.n += 10

    @rx.event
    def on_prog(self, p: dict):
        self.prog.append(str(round(p.get("progress", 0), 2)))

    @rx.event
    def mark(self, what: str):
        self.done.append(what)


def index():
    up = lambda h: h(rx.upload_files(upload_id="u", on_upload_progress=S.on_prog))  # noqa: E731
    return rx.vstack(
        rx.heading("upfail", id="h"),
        rx.upload(rx.text("drop"), id="u"),
        rx.text(rx.selected_files("u").join(","), id="sel"),
        rx.button("fail now", on_click=up(S.fail_now), id="b-now"),
        rx.button("fail later", on_click=up(S.fail_later), id="b-later"),
        rx.button("ok", on_click=up(S.ok), id="b-ok"),
        rx.button("ping", on_click=S.mark("ping"), id="b-ping"),
        rx.text("n=", S.n, id="n"),
        rx.text("prog=", S.prog.join(","), id="prog"),
        rx.text("done=", S.done.join(","), id="done"),
    )


app = rx.App()
app.add_page(index)
