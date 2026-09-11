"""Module B: same component name, byte-identical render, different event handler."""
import reflex as rx


@rx.memo
def card(label: str) -> rx.Component:
    return rx.box(rx.text(label), id="card")
