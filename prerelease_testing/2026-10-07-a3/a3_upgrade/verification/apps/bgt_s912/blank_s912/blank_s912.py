"""verify_upgrade A3-06: background-task writes to INHERITED vars outside `async with self`."""

import reflex as rx

assert "/scratchpad/envs/stable/" in rx.__file__, rx.__file__


class Base(rx.State):
    count: int = 0
    items: list[str] = []

    @rx.event
    def inc(self):
        self.count += 1


class Mid(Base):
    level2: int = 0


class Worker(Mid):
    own: int = 0
    status: str = ""

    @rx.event
    def own_handler_writes_inherited(self):
        self.count += 1000

    @rx.event
    def own_handler_writes_own(self):
        self.own += 1000

    async def _report(self, case: str, fn):
        try:
            fn()
            res = "ok"
        except Exception as e:  # noqa: BLE001
            res = f"{type(e).__name__}"
        async with self:
            self.status = f"{case}={res}"

    @rx.event(background=True)
    async def bg_write_inherited(self):
        def f():
            self.count += 10
        await self._report("write_inherited", f)

    @rx.event(background=True)
    async def bg_write_grandparent_via_mid(self):
        def f():
            self.level2 += 10
        await self._report("write_mid_var", f)

    @rx.event(background=True)
    async def bg_write_own(self):
        def f():
            self.own += 10
        await self._report("write_own", f)

    @rx.event(background=True)
    async def bg_append_inherited(self):
        def f():
            self.items.append("x")
        await self._report("append_inherited", f)

    @rx.event(background=True)
    async def bg_call_inherited_handler(self):
        def f():
            self.inc()
        await self._report("call_inherited_handler", f)

    @rx.event(background=True)
    async def bg_call_own_handler_inherited(self):
        def f():
            self.own_handler_writes_inherited()
        await self._report("own_handler_writes_inherited", f)

    @rx.event(background=True)
    async def bg_call_own_handler_own(self):
        def f():
            self.own_handler_writes_own()
        await self._report("own_handler_writes_own", f)

    @rx.event(background=True)
    async def bg_locked_control(self):
        async with self:
            self.count += 1
            self.items.append("L")
            self.status = "locked_control=ok"

    @rx.event
    def noop(self):
        pass


def index() -> rx.Component:
    return rx.vstack(
        rx.text(Base.count.to_string(), id="count"),
        rx.text(Mid.level2.to_string(), id="level2"),
        rx.text(Worker.own.to_string(), id="own"),
        rx.text(Base.items.length().to_string(), id="items"),
        rx.text(Worker.status, id="status"),
        *[
            rx.button(n, id=n, on_click=getattr(Worker, n))
            for n in [
                "bg_write_inherited",
                "bg_write_grandparent_via_mid",
                "bg_write_own",
                "bg_append_inherited",
                "bg_call_inherited_handler",
                "bg_call_own_handler_inherited",
                "bg_call_own_handler_own",
                "bg_locked_control",
                "noop",
            ]
        ],
    )


app = rx.App()
app.add_page(index)
