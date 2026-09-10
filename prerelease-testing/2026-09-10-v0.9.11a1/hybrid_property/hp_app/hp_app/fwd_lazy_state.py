"""Python 3.14 only: PEP 649 lazy annotations (no `from __future__ import annotations`)."""

import dataclasses
from typing import TYPE_CHECKING

import reflex as rx

if TYPE_CHECKING:
    from decimal import Decimal as LazyUnresolvable


@dataclasses.dataclass
class LazyItem:
    name: str
    tag: "LazyTag | None" = None


@dataclasses.dataclass
class LazyTag:
    label: str


@dataclasses.dataclass
class LazyWeighted:
    name: str
    weight: LazyUnresolvable | None = None  # noqa: F821  # lazily evaluated on 3.14


class LazyState(rx.State):
    items: list[LazyItem] = []
    weighted: LazyWeighted = LazyWeighted(name="lw")
    label: str = "lazy"

    @rx.var
    def item_count(self) -> int:
        return len(self.items)

    @rx.var
    def weighted_name(self) -> str:
        return self.weighted.name

    @rx.event
    def add(self):
        self.items.append(LazyItem(name=f"l{len(self.items)}", tag=LazyTag(label="lt")))


def lazy_page() -> rx.Component:
    return rx.vstack(
        rx.heading("lazy annotations (3.14)"),
        rx.el.input(id="token", value=LazyState.router.session.client_token, read_only=True),
        rx.text(LazyState.item_count, id="item_count"),
        rx.text(LazyState.weighted_name, id="weighted_name"),
        rx.hstack(
            rx.foreach(LazyState.items, lambda it: rx.text(it.name, "/", it.tag.label, class_name="item")),  # pyright: ignore[reportOptionalMemberAccess]
            id="items",
        ),
        rx.button("add", on_click=LazyState.add, id="btn_add"),
        spacing="2",
        padding="1em",
    )
