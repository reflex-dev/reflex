"""PEP 695 `type` statement aliases as state var / event handler annotations.

Requires Python 3.12+. Exercises reflex-base PR #6944 shapes:
- plain alias (type Name = str)
- Literal alias (type Key = Literal[...])
- parameterized generic alias (Items[str] for type Items[T] = list[T])
- multi-param generic alias (Pair[str, int] for type Pair[K, V] = dict[K, V])
- alias in a union (Key | None) and alias-of-alias (type MaybeKey = Key | None)
- variadic alias (type Tup[*Ts] = tuple[*Ts])
- alias used in event handler arg annotations
- alias-typed vars driven through rx.foreach / rx.cond
"""

from typing import Literal

import reflex as rx

type Name = str
type Key = Literal["day", "week", "month"]
type Items[T] = list[T]
type Pair[K, V] = dict[K, V]
type MaybeKey = Key | None
type Tup[*Ts] = tuple[*Ts]


class AliasState(rx.State):
    """State whose vars are all annotated via PEP 695 aliases."""

    name: Name = "reflex"
    key: Key = "day"
    entries: Items[str] = ["alpha", "beta"]
    union_key: Key | None = None
    nested_key: MaybeKey = None
    scores: Pair[str, int] = {"alpha": 1, "beta": 2}
    pos: Tup[int, str] = (7, "seven")

    @rx.event
    def choose_key(self, value: Key):
        """Set key from a value annotated with a Literal alias.

        Args:
            value: The new key.
        """
        self.key = value
        self.union_key = value
        self.nested_key = value

    @rx.event
    def rename(self, value: Name):
        """Set name from a plain-alias-annotated arg.

        Args:
            value: The new name.
        """
        self.name = value

    @rx.event
    def add_entry(self, form_data: Pair[str, str]):
        """Add an entry from a form; arg annotated with generic dict alias.

        Args:
            form_data: The submitted form data.
        """
        item = form_data.get("item", "")
        if item:
            self.entries = [*self.entries, item]
            self.scores[item] = len(self.entries)

    @rx.event
    def clear_union(self):
        """Reset the union-typed keys to None."""
        self.union_key = None
        self.nested_key = None


def index() -> rx.Component:
    """The main page.

    Returns:
        The page component.
    """
    return rx.container(
        rx.vstack(
            rx.heading("PEP695 alias app", id="title"),
            rx.text("name: ", AliasState.name, id="name"),
            rx.text("key: ", AliasState.key, id="key"),
            rx.text(
                "union: ",
                rx.cond(AliasState.union_key, AliasState.union_key, "none"),
                id="union",
            ),
            rx.text(
                "nested: ",
                rx.cond(AliasState.nested_key, AliasState.nested_key, "none"),
                id="nested",
            ),
            rx.text("pos: ", AliasState.pos.to_string(), id="pos"),
            rx.hstack(
                rx.button("day", on_click=AliasState.choose_key("day"), id="btn-day"),
                rx.button(
                    "week", on_click=AliasState.choose_key("week"), id="btn-week"
                ),
                rx.button(
                    "month", on_click=AliasState.choose_key("month"), id="btn-month"
                ),
                rx.button("clear", on_click=AliasState.clear_union, id="btn-clear"),
            ),
            # NOTE: on_change=AliasState.choose_key (uncalled) crashes compile:
            # "TypeError: Could not compare types <class 'str'> and Key" --
            # typehint_issubclass does not resolve TypeAliasType (see
            # repro_alias_event_arg.py). Lambda wrapper is the workaround.
            rx.select(
                ["day", "week", "month"],
                value=AliasState.key,
                on_change=lambda v: AliasState.choose_key(v),
            ),
            rx.input(
                placeholder="rename",
                on_change=lambda v: AliasState.rename(v),
                id="name-input",
            ),
            rx.form(
                rx.hstack(
                    rx.input(placeholder="new entry", name="item", id="entry-input"),
                    rx.button("add", type="submit", id="entry-submit"),
                ),
                # on_submit=AliasState.add_entry (uncalled) also crashes:
                # EventHandlerArgTypeMismatchError ... got Pair[str, str]
                on_submit=lambda d: AliasState.add_entry(d),
                reset_on_submit=True,
            ),
            rx.hstack(
                rx.foreach(AliasState.entries, lambda e: rx.badge(e)),
                id="entries",
            ),
            rx.vstack(
                rx.foreach(
                    AliasState.scores.items(),
                    lambda kv: rx.text(kv[0], "=", kv[1].to_string()),
                ),
                id="scores",
            ),
        ),
    )


app = rx.App()
app.add_page(index)
