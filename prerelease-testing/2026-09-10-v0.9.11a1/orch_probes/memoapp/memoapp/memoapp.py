import dataclasses
import enum

import reflex as rx

from .pkg import a, b


class Kind(enum.IntEnum):
    ONE = 1
    TWO = 2


@dataclasses.dataclass
class Alpha:
    a: str = "x"


@dataclasses.dataclass
class Beta:
    a: str = "x"


class CustomA(rx.Fragment):
    """Two components differing only in module-level custom code."""

    def add_custom_code(self) -> list[str]:
        return ["if (typeof window !== 'undefined') { window.__memo_probe_a = 'A'; }"]


class CustomB(rx.Fragment):
    def add_custom_code(self) -> list[str]:
        return ["if (typeof window !== 'undefined') { window.__memo_probe_b = 'B'; }"]


@rx.memo
def shaped(alpha: str) -> rx.Component:
    return rx.text(alpha)


class S(rx.State):
    label: str = "hello"
    n: int = 0

    @rx.event
    def bump(self):
        self.n += 1


def index() -> rx.Component:
    return rx.vstack(
        a.card(label=S.label),
        b.card(label=S.label),
        CustomA.create(rx.text("custom-a")),
        CustomB.create(rx.text("custom-b")),
        rx.text(f"alpha={Alpha().a}", id="alpha"),
        rx.text(f"beta={Beta().a}", id="beta"),
        rx.text(f"kind_one={Kind.ONE.value}", id="kind"),
        rx.text(f"n={S.n}", id="n"),
        rx.button("bump", on_click=S.bump, id="bump"),
    )


app = rx.App()
app.add_page(index, route="/")
