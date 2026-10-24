"""Many-substate app (#7441 / reflex#7429): BIG_N state classes, all read on one page.

BIG_N=3000 is the "Maximum call stack size exceeded" case; BIG_N=200 is the mid-size
render-time comparison. BIG_READ limits how many substates the page reads.
"""

import os

import reflex as rx

assert f"/envs/{os.environ.get('EXPECT_VENV', 'new')}/" in rx.__file__, rx.__file__

N = int(os.environ.get("BIG_N", "3000"))
READ = int(os.environ.get("BIG_READ", str(N)))


class Root(rx.State):
    ticks: int = 0

    @rx.event
    async def bump_some(self):
        # Touch three substates in one event: the deltas must land only there.
        for i in (0, READ // 2, READ - 1):
            sub = await self.get_state(SUBS[i])
            sub.v += 1
        self.ticks += 1


def inc(self):
    self.v += 1


SUBS: list[type[Root]] = []
for _i in range(N):
    _cls = type(
        f"S{_i}",
        (Root,),
        {"__annotations__": {"v": int}, "v": _i, "inc": rx.event(inc), "__module__": __name__},
    )
    SUBS.append(_cls)


def index() -> rx.Component:
    return rx.el.div(
        rx.el.div(rx.State.is_hydrated.to_string(), id="hydrated"),
        rx.el.span(Root.ticks, id="ticks"),
        rx.el.button("bump", id="bump", on_click=Root.bump_some),
        rx.el.button("inc-last", id="inc-last", on_click=SUBS[READ - 1].inc),
        rx.el.div(*[rx.el.span(S.v, class_name="v") for S in SUBS[:READ]], id="vals"),
    )


app = rx.App()
app.add_page(index, route="/")
