"""Module A: a memo component whose render is identical to the one in module B."""
import reflex as rx


@rx.memo
def card(label: str) -> rx.Component:
    return rx.box(rx.text(label), id="card")
