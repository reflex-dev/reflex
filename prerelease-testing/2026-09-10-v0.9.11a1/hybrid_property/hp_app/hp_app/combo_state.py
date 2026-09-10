"""Page 3: hybrid properties combined with ComponentState, @rx.memo, client_state,
computed vars depending on a hybrid property, and background tasks using the setter."""

import asyncio

import reflex as rx
from reflex.experimental import hybrid_property


class ComboState(rx.State):
    first: str = "a"
    last: str = "b"
    n: int = 3
    log: list[str] = []

    @hybrid_property
    def full_label(self) -> str:
        return f"{self.first}-{self.last}"

    @full_label.setter
    def _set_full_label(self, value: str) -> None:
        self.first, self.last = value.split("-", 1)

    @hybrid_property
    def doubled(self) -> int:
        return self.n * 2

    # computed var that depends on hybrid properties (dependency tracking must see
    # first/last/n through the property getters)
    @rx.var
    def summary(self) -> str:
        return f"{self.full_label.upper()}#{self.doubled}"

    @rx.event
    def set_first(self, value: str):
        self.first = value

    @rx.event
    def inc_n(self):
        self.n += 1

    @rx.event(background=True)
    async def bg_rename(self):
        await asyncio.sleep(0.3)
        async with self:
            self.full_label = "bg-task"  # setter through the StateProxy
            self.log.append(f"bg:{self.full_label}")  # getter through the proxy
        await asyncio.sleep(0.3)
        async with self:
            self.n = 10
            self.log.append(f"bg:doubled={self.doubled}")


class Counter(rx.ComponentState):
    count: int = 0
    step: int = 2

    @hybrid_property
    def display(self) -> str:
        return f"count={self.count}"

    @hybrid_property
    def next_value(self) -> int:
        return self.count + self.step

    @next_value.setter
    def _set_next_value(self, value: int) -> None:
        self.count = value - self.step

    @rx.var
    def display_backend(self) -> str:
        return self.display

    @rx.event
    def bump(self):
        self.count += 1

    @rx.event
    def jump(self, value: int):
        self.next_value = value

    @classmethod
    def get_component(cls, **props) -> rx.Component:
        return rx.vstack(
            rx.text(cls.display, class_name="cs_display"),
            rx.text(cls.display_backend, class_name="cs_display_backend"),
            rx.text(cls.next_value, class_name="cs_next"),
            rx.hstack(
                rx.button("bump", on_click=cls.bump, class_name="cs_bump"),
                rx.button("jump", on_click=cls.jump(10), class_name="cs_jump"),
            ),
            **props,
        )


counter = Counter.create


@rx.memo
def badge(label: rx.Var[str], n: rx.Var[int]) -> rx.Component:
    return rx.el.span(label, ":", n, id="memo_badge")


def combo_page() -> rx.Component:
    note = rx._x.client_state(default="note", var_name="note")
    return rx.vstack(
        rx.heading("combo"),
        rx.el.input(id="token", value=ComboState.router.session.client_token, read_only=True),
        rx.text(ComboState.full_label, id="full_label"),
        rx.text(ComboState.doubled, id="doubled"),
        rx.text(ComboState.summary, id="summary"),
        badge(label=ComboState.full_label, n=ComboState.doubled),
        rx.el.input(id="note_input", on_change=note.set_value),
        rx.text(f"{ComboState.full_label} / {note.value}", id="mixed"),
        rx.hstack(
            rx.button("set_first", on_click=ComboState.set_first("zz"), id="btn_set_first"),
            rx.button("inc_n", on_click=ComboState.inc_n, id="btn_inc_n"),
            rx.button("bg_rename", on_click=ComboState.bg_rename, id="btn_bg"),
        ),
        rx.text(ComboState.log.join(" | "), id="log"),
        rx.hstack(counter(id="c1"), counter(id="c2"), id="counters"),
        rx.link("dc", href="/dc"),
        spacing="2",
        padding="1em",
    )
