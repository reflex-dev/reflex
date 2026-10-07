"""Upgrade guide (upgrading-to-0-10.md @ 555b667c1) samples, run as written, plus instrumentation.

/sample    the section-1 sample verbatim (0.10 only: default_value() does not exist on 0.9)
/portable  the get_fields()[...].default_value() recipe (0.9 and 0.10)
/bg        section 3: Parent/Child verbatim + variants that record what happened
/defaults  section 2 warning: a default assigned at runtime only affects the worker process that ran it
"""

import importlib.metadata
import os
from typing import ClassVar

import reflex as rx

REFLEX_VERSION = importlib.metadata.version("reflex")
IS_010 = REFLEX_VERSION.startswith("0.10")


# ---- section 1 sample, verbatim -------------------------------------------------------------------------
class State(rx.State):
    _items: list[str] = ["a", "b"]
    _endpoint: ClassVar[str] = "https://example.com/api"


def page():
    return rx.vstack(
        # 0.9: rx.foreach(State._items, rx.text) baked in the default.
        rx.foreach(State._items.default_value(), rx.text),
        rx.text(State._endpoint),
    )


def portable():
    return rx.vstack(
        rx.foreach(State.get_fields()["_items"].default_value(), rx.text),
        rx.text(State._endpoint),
        rx.text(f"reflex {REFLEX_VERSION}", id="ver"),
    )


# ---- section 3 sample, verbatim (Parent/Child) + instrumented variants ---------------------------------
class Parent(rx.State):
    count: int = 0

    @rx.event
    def bump(self):
        self.count += 1


class Child(Parent):
    @rx.event(background=True)
    async def work(self):
        self.bump()  # Raises ImmutableStateError on 0.10.


class Child2(Parent):
    result: str = ""
    log: list[str] = []
    own: int = 0

    @rx.event
    def own_var_bump(self):
        self.own += 1

    @rx.event(background=True)
    async def work_own_var_outside(self):
        try:
            self.own_var_bump()
            outcome = "no error"
        except Exception as e:  # noqa: BLE001
            outcome = type(e).__name__
        async with self:
            self.result = f"own-var outside: {outcome}"

    @rx.event
    def peek(self):
        return self.count

    @rx.event
    def whoami(self):
        self.log.append(
            f"type(self)={type(self).__name__} self.__class__={self.__class__.__name__} "
            f"isinstance(self, Parent)={isinstance(self, Parent)}"
        )

    @rx.event
    def own_bump(self):
        self.count += 10

    @rx.event(background=True)
    async def work_outside(self):
        try:
            self.bump()
            outcome = "no error"
        except Exception as e:  # noqa: BLE001
            outcome = type(e).__name__
        async with self:
            self.result = f"outside: {outcome}"

    @rx.event(background=True)
    async def work_inside(self):
        async with self:
            self.bump()
            self.result = "inside: ok"

    @rx.event(background=True)
    async def work_readonly(self):
        try:
            v = self.peek()
            outcome = f"ran, returned {v!r}"
        except Exception as e:  # noqa: BLE001
            outcome = f"{type(e).__name__}"
        async with self:
            self.result = f"readonly outside: {outcome}"

    @rx.event(background=True)
    async def work_type(self):
        async with self:
            self.whoami()
            self.result = "type: " + (self.log[-1] if self.log else "<nothing logged>")

    @rx.event(background=True)
    async def work_own_outside(self):
        try:
            self.own_bump()
            outcome = "no error"
        except Exception as e:  # noqa: BLE001
            outcome = type(e).__name__
        async with self:
            self.result = f"own outside: {outcome}"

    @rx.event(background=True)
    async def work_direct_inherited(self):
        try:
            self.count += 100  # inherited var, written directly outside `async with self`
            outcome = "no error"
        except Exception as e:  # noqa: BLE001
            outcome = type(e).__name__
        async with self:
            self.result = f"direct inherited write outside: {outcome}"

    @rx.event(background=True)
    async def work_direct_own(self):
        try:
            self.own += 100  # own var, written directly outside `async with self`
            outcome = "no error"
        except Exception as e:  # noqa: BLE001
            outcome = type(e).__name__
        async with self:
            self.result = f"direct own write outside: {outcome}"

    @rx.event
    def refresh(self):
        pass


class Child3(Parent):
    """The documented fix, verbatim."""

    @rx.event(background=True)
    async def work(self):
        async with self:
            self.bump()


def bg():
    return rx.vstack(
        rx.heading("bg"),
        rx.text("child count: ", rx.text.span(Child2.count, id="c2count")),
        rx.text("child (verbatim) count: ", rx.text.span(Child.count, id="c1count")),
        rx.text("child3 (fix) count: ", rx.text.span(Child3.count, id="c3count")),
        rx.text("parent count: ", rx.text.span(Parent.count, id="pcount")),
        rx.text(Child2.result, id="result"),
        rx.button("verbatim work", on_click=Child.work, id="b_verbatim"),
        rx.button("verbatim fix", on_click=Child3.work, id="b_fix"),
        rx.button("outside", on_click=Child2.work_outside, id="b_outside"),
        rx.button("inside", on_click=Child2.work_inside, id="b_inside"),
        rx.button("readonly", on_click=Child2.work_readonly, id="b_readonly"),
        rx.button("type", on_click=Child2.work_type, id="b_type"),
        rx.button("own outside", on_click=Child2.work_own_outside, id="b_own"),
        rx.button("own var outside", on_click=Child2.work_own_var_outside, id="b_own_var"),
        rx.button("direct inherited", on_click=Child2.work_direct_inherited, id="b_direct_inh"),
        rx.button("direct own", on_click=Child2.work_direct_own, id="b_direct_own"),
        rx.text("own: ", rx.text.span(Child2.own, id="own")),
        rx.button("refresh", on_click=Child2.refresh, id="b_refresh"),
    )


# ---- section 2 warning: runtime default assignment is per worker --------------------------------------
class Defaults(rx.State):
    level: int = 20
    pid: str = ""

    @rx.event
    def reconf(self):
        type(self).level = 77
        self.pid = str(os.getpid())

    @rx.event
    def whoami(self):
        self.pid = str(os.getpid())


def defaults():
    return rx.vstack(
        rx.text("level: ", rx.text.span(Defaults.level, id="level")),
        rx.text("pid: ", rx.text.span(Defaults.pid, id="pid")),
        rx.button("reconf", on_click=Defaults.reconf, id="b_reconf"),
        rx.button("whoami", on_click=Defaults.whoami, id="b_whoami"),
    )


app = rx.App()
if IS_010:
    app.add_page(page, route="/sample")
app.add_page(portable, route="/portable")
app.add_page(bg, route="/bg")
app.add_page(defaults, route="/defaults")
app.add_page(portable, route="/")
