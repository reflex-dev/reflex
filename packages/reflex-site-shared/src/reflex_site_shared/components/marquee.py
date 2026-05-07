"""Marquee module."""

from typing import Literal

import reflex as rx


class Marquee(rx.NoSSRComponent):
    """Marquee component."""

    library = "react-fast-marquee@1.6.5"
    tag = "Marquee"
    is_default = True

    # Behavior props
    auto_fill: rx.Var[bool] = rx.Var.create(True)
    play: rx.Var[bool] = rx.Var.create(True)
    pause_on_hover: rx.Var[bool] = rx.Var.create(True)
    pause_on_click: rx.Var[bool] = rx.Var.create(False)
    direction: rx.Var[Literal["left", "right", "up", "down"]] = rx.Var.create("left")

    # Animation props
    speed: rx.Var[int] = rx.Var.create(35)
    delay: rx.Var[int] = rx.Var.create(0)
    loop: rx.Var[int] = rx.Var.create(0)

    # Gradient props
    gradient: rx.Var[bool] = rx.Var.create(True)
    gradient_color: rx.Var[str] = rx.Var.create("var(--c-slate-1)")
    gradient_width: rx.Var[int | str] = rx.Var.create(250)


marquee = Marquee.create
