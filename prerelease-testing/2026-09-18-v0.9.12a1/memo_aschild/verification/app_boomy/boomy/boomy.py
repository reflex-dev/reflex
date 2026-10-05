"""Minimal repro app for verifier issue 2: eager evaluation of rx.cond branches."""

import os

import reflex as rx

assert "/envs/" in rx.__file__, rx.__file__


class S(rx.State):
    """Flag state (always False unless toggled)."""

    flag: bool = False
    user: dict[str, str] | None = None

    @rx.event
    def toggle(self):
        """Flip the flag."""
        self.flag = not self.flag


@rx.memo
def crashing_memo() -> rx.Component:
    """A memo component whose own render body throws.

    Returns:
        The component.
    """
    return rx.text(rx.Var("undefined_global_thing.nope", _var_type=str))


def ok_page() -> rx.Component:
    """Healthy control page.

    Returns:
        The component.
    """
    return rx.container(rx.text("healthy", id="ok"))


def boomvar_page() -> rx.Component:
    """Inline raw-JS Var referencing an undefined global in the FALSE branch.

    Returns:
        The component.
    """
    crash = (
        rx.text(rx.Var("undefined_global_thing.nope", _var_type=str))
        if os.environ.get("QA_VAR") == "1"
        else rx.text("var-crash disabled", id="disabled")
    )
    return rx.container(
        rx.heading("boomvar"),
        rx.cond(S.flag, rx.box(crash, id="crash_box"), rx.text("not exploded", id="ok_text")),
    )


def boommemo_page() -> rx.Component:
    """A memo COMPONENT that throws in its own render, in the FALSE branch.

    Returns:
        The component.
    """
    return rx.container(
        rx.heading("boommemo"),
        rx.cond(
            S.flag,
            rx.box(crashing_memo(), id="crash_box"),
            rx.text("not exploded", id="ok_text"),
        ),
    )


def boomnull_page() -> rx.Component:
    """Idiomatic null-guard: deref a None state var inside the untaken branch.

    Returns:
        The component.
    """
    return rx.container(
        rx.heading("boomnull"),
        rx.cond(
            S.user,
            rx.text("hello ", S.user["name"]),
            rx.text("not exploded", id="ok_text"),
        ),
    )


app = rx.App()
app.add_page(ok_page, route="/")
app.add_page(boomvar_page, route="/boomvar")
app.add_page(boommemo_page, route="/boommemo")
app.add_page(boomnull_page, route="/boomnull")
