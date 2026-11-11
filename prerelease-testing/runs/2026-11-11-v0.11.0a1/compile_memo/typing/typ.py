"""Typing checks for #7750 (rx.match), #7716 (callout icon), #7753 (code_block text)."""
import reflex as rx


class S(rx.State):
    kind: str = "a"
    flag: bool = True


def as_component() -> rx.Component:
    # first case returns a component -> rx.match should type as Component
    return rx.match(S.kind, ("a", rx.text("A")), ("b", rx.text("B")), rx.text("other"))


def as_var() -> rx.Var[str]:
    return rx.match(S.kind, ("a", "A"), ("b", "B"), "other")


def mixed() -> rx.Component:
    # first case str, default component: what does the checker say?
    return rx.match(S.kind, ("a", "A"), rx.text("other"))


def callouts() -> list[rx.Component]:
    return [
        rx.callout("x", icon=rx.icon("info")),
        rx.callout("x", icon=rx.cond(S.flag, rx.icon("check"), rx.icon("x"))),
        rx.callout("x", icon="info"),
        rx.code_block("t", language="text"),
    ]


reveal_type(rx.match(S.kind, ("a", rx.text("A")), rx.text("o")))
reveal_type(rx.match(S.kind, ("a", "A"), "o"))
