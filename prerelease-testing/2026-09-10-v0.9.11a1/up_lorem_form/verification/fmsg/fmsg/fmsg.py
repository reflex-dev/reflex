"""Independent verification of the FormMessage-without-name claim.

Five pages, each a small rx.form variant, so one run tells us exactly which
shape blows up.
"""

import reflex as rx

assert "/envs/" in rx.__file__, rx.__file__
print("VERIFY reflex module:", rx.__file__)


class S(rx.State):
    force: bool = False
    submitted: str = ""

    @rx.event
    def submit(self, data: dict):
        self.submitted = repr(data)
        self.force = not data.get("who")


def msg(**kwargs) -> rx.Component:
    return rx.form.message(
        "This field is required.",
        match="valueMissing",
        force_match=S.force,
        color=rx.color("tomato", 10),
        **kwargs,
    )


@rx.page(route="/unnamed")
def unnamed() -> rx.Component:
    """form.field WITHOUT name=, containing a form.message (the claim)."""
    return rx.vstack(
        rx.heading("unnamed", id="hd"),
        rx.form(
            rx.form.field(
                rx.card(
                    rx.text("Who are you?"),
                    rx.input(placeholder="name", name="who", id="inp"),
                    msg(),
                ),
            ),
            rx.button("Submit", type="submit", id="sub"),
            on_submit=S.submit,
        ),
        rx.text(S.submitted, id="out"),
    )


@rx.page(route="/named")
def named() -> rx.Component:
    """Identical, but name= on form.field."""
    return rx.vstack(
        rx.heading("named", id="hd"),
        rx.form(
            rx.form.field(
                rx.card(
                    rx.text("Who are you?"),
                    rx.input(placeholder="name", name="who", id="inp"),
                    msg(),
                ),
                name="who",
            ),
            rx.button("Submit", type="submit", id="sub"),
            on_submit=S.submit,
        ),
        rx.text(S.submitted, id="out"),
    )


@rx.page(route="/msgname")
def msgname() -> rx.Component:
    """Unnamed form.field, but the message carries its own name=."""
    return rx.vstack(
        rx.heading("msgname", id="hd"),
        rx.form(
            rx.form.field(
                rx.card(
                    rx.text("Who are you?"),
                    rx.input(placeholder="name", name="who", id="inp"),
                    msg(name="who"),
                ),
            ),
            rx.button("Submit", type="submit", id="sub"),
            on_submit=S.submit,
        ),
        rx.text(S.submitted, id="out"),
    )


@rx.page(route="/nomsg")
def nomsg() -> rx.Component:
    """Unnamed form.field with NO form.message child."""
    return rx.vstack(
        rx.heading("nomsg", id="hd"),
        rx.form(
            rx.form.field(
                rx.card(
                    rx.text("Who are you?"),
                    rx.input(placeholder="name", name="who", id="inp"),
                ),
            ),
            rx.button("Submit", type="submit", id="sub"),
            on_submit=S.submit,
        ),
        rx.text(S.submitted, id="out"),
    )


@rx.page(route="/msgtop")
def msgtop() -> rx.Component:
    """form.message directly under rx.form, no field, no name."""
    return rx.vstack(
        rx.heading("msgtop", id="hd"),
        rx.form(
            rx.card(
                rx.text("Who are you?"),
                rx.input(placeholder="name", name="who", id="inp"),
                msg(),
            ),
            rx.button("Submit", type="submit", id="sub"),
            on_submit=S.submit,
        ),
        rx.text(S.submitted, id="out"),
    )


@rx.page(route="/labelonly")
def labelonly() -> rx.Component:
    """Unnamed form.field containing only a form.label (no message at all)."""
    return rx.vstack(
        rx.heading("labelonly", id="hd"),
        rx.form(
            rx.form.field(
                rx.card(
                    rx.form.label("Who are you?"),
                    rx.input(placeholder="name", name="who", id="inp"),
                ),
            ),
            rx.button("Submit", type="submit", id="sub"),
            on_submit=S.submit,
        ),
        rx.text(S.submitted, id="out"),
    )


@rx.page(route="/controlonly")
def controlonly() -> rx.Component:
    """Unnamed form.field containing only a form.control (the docs' anatomy, minus name)."""
    return rx.vstack(
        rx.heading("controlonly", id="hd"),
        rx.form(
            rx.form.field(
                rx.card(
                    rx.text("Who are you?"),
                    rx.form.control(
                        rx.input(placeholder="name", name="who", id="inp"),
                        as_child=True,
                    ),
                ),
            ),
            rx.button("Submit", type="submit", id="sub"),
            on_submit=S.submit,
        ),
        rx.text(S.submitted, id="out"),
    )


app = rx.App()
