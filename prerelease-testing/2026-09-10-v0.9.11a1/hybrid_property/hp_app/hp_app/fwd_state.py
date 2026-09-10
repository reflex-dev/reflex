"""Page 5: forward references (#6929).

`from __future__ import annotations`; `Item.tag` references `Tag`, defined later in the
module (resolvable once the module is loaded); `Weighted.weight` references a name only
a type checker can resolve, so `get_type_hints(Weighted)` raises NameError at runtime.
`Weighted` is exercised by scripts/probe_fwd_mock.py (mock.patch.object /
inspect.iscoroutinefunction probes) and only reaches the UI through a computed var.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

import reflex as rx
from reflex.experimental import hybrid_property

if TYPE_CHECKING:
    from decimal import Decimal as Unresolvable  # only importable for type checkers


@dataclasses.dataclass
class Item:
    name: str
    qty: int = 1
    tag: Tag | None = None


@dataclasses.dataclass
class Tag:
    label: str


@dataclasses.dataclass
class Weighted:
    name: str
    weight: Unresolvable | None = None


class FwdState(rx.State):
    items: list[Item] = []
    current: Item | None = None
    weighted: Weighted = Weighted(name="w")
    label: str = "fwd"

    @hybrid_property
    def banner(self) -> str:
        return f"{self.label}:{self.label}"

    @rx.var
    def item_count(self) -> int:
        return len(self.items)

    @rx.var
    def weighted_name(self) -> str:
        return self.weighted.name

    @rx.event
    def add(self):
        item = Item(name=f"i{len(self.items)}", tag=Tag(label=f"t{len(self.items)}"))
        self.items.append(item)
        self.current = item

    @rx.event
    async def async_add(self):
        self.add()


def fwd_page() -> rx.Component:
    return rx.vstack(
        rx.heading("forward refs"),
        rx.el.input(id="token", value=FwdState.router.session.client_token, read_only=True),
        rx.text(FwdState.banner, id="banner"),
        rx.text(FwdState.item_count, id="item_count"),
        rx.text(FwdState.weighted_name, id="weighted_name"),
        rx.cond(
            FwdState.current,
            rx.text(FwdState.current.name, "/", FwdState.current.tag.label, id="current"),  # pyright: ignore[reportOptionalMemberAccess]
            rx.text("-", id="current"),
        ),
        rx.hstack(
            rx.foreach(FwdState.items, lambda it: rx.text(it.name, class_name="item")),
            id="items",
        ),
        rx.hstack(
            rx.button("add", on_click=FwdState.add, id="btn_add"),
            rx.button("async_add", on_click=FwdState.async_add, id="btn_async_add"),
        ),
        rx.link("core", href="/"),
        spacing="2",
        padding="1em",
    )
