"""Inferred types for `reflex_components_core` helpers that are part of the public contract."""

from typing import assert_type

import reflex as rx
from reflex.state import State
from reflex.vars.base import Var


class _MatchState(State):
    value: str = "a"


# `rx.match` builds a component when its cases return components, and a Var
# when they return values, so a function wrapping it can declare either.
def _match_component() -> rx.Component:
    return rx.match(
        _MatchState.value,
        ("a", rx.text("A")),
        ("b", "c", rx.text("B or C")),
        rx.text("default"),
    )


def _match_var() -> Var:
    return rx.match(_MatchState.value, ("a", "red"), ("b", "c", "blue"), "gray")


assert_type(
    rx.match(_MatchState.value, ("a", rx.text("A")), rx.text("default")),
    rx.Component,
)
assert_type(rx.match(_MatchState.value, ("a", 1), 0), Var)
