"""Delta-shape probe across state managers (memory / redis / prod+2 workers).

Covers: substate deltas, @rx.var(cache=False) incl. one withheld by a get_delta
override (#7216 / FINDING-003), rx._x.client_state, a background task using
`async with self`, and an event chain across substates.
"""

import asyncio

import reflex as rx


class Root(rx.State):
    """Root state with a get_delta override that withholds an uncached var."""

    visible: bool = False
    n: int = 0

    @rx.var(cache=False)
    def uncached_n(self) -> str:
        return f"U{self.n}"

    @rx.var(cache=True)
    def cached_n(self) -> str:
        return f"C{self.n}"

    @rx.event
    def bump(self):
        self.n += 1

    @rx.event
    def show(self):
        self.visible = True

    @rx.event
    def hide(self):
        self.visible = False



class Sub(Root):
    count: int = 0
    log: list[str] = []
    running: bool = False

    @rx.var(cache=False)
    def sub_uncached(self) -> str:
        return f"S{self.count}"

    @rx.event
    def sbump(self):
        self.count += 1

    @rx.event
    def chain(self):
        self.log = [*self.log, "chain"]
        yield Other.obump
        yield Root.bump

    @rx.event(background=True)
    async def storm(self):
        async with self:
            if self.running:
                return
            self.running = True
        for _ in range(5):
            async with self:
                self.count += 1
            await asyncio.sleep(0.15)
        async with self:
            self.running = False
            self.log = [*self.log, "storm-done"]


class Other(rx.State):
    ocount: int = 0

    @rx.event
    def obump(self):
        self.ocount += 1



# Downstream packages patch `get_delta` after class creation (the name is
# reserved as an event-handler name on every version); this is the
# reflex-enterprise auth-filter shape: withhold `uncached_n` until `visible`.
_orig_get_delta = Root.get_delta


def _filtered_get_delta(self):
    delta = _orig_get_delta(self)
    if not self.visible:
        key = self.get_full_name()
        mine = delta.get(key)
        if mine and any(k.startswith("uncached_n") for k in mine):
            mine = {k: v for k, v in mine.items() if not k.startswith("uncached_n")}
            delta = dict(delta)
            if mine:
                delta[key] = mine
            else:
                delta.pop(key)
    return delta


Root.get_delta = _filtered_get_delta


cs = rx._x.client_state(default="", var_name="dcs")


def index() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.button("bump", on_click=Root.bump, id="b_bump"),
            rx.button("sbump", on_click=Sub.sbump, id="b_sbump"),
            rx.button("chain", on_click=Sub.chain, id="b_chain"),
            rx.button("storm", on_click=Sub.storm, id="b_storm"),
            rx.button("show", on_click=Root.show, id="b_show"),
            rx.button("hide", on_click=Root.hide, id="b_hide"),
        ),
        rx.text(Root.uncached_n, id="v_unc"),
        rx.text(Root.cached_n, id="v_cac"),
        rx.text(Sub.sub_uncached, id="v_sunc"),
        rx.text(Sub.count.to_string(), id="v_scount"),
        rx.text(Other.ocount.to_string(), id="v_ocount"),
        rx.text(Sub.log.length().to_string(), id="v_loglen"),
        rx.text(Root.visible.to_string(), id="v_vis"),
        cs,
        rx.input(value=cs.value, on_change=cs.set_value, id="cs_in"),
        rx.text(cs.value, id="v_cs"),
    )


app = rx.App()
app.add_page(index, route="/")
