"""Minimal isolation of the form-designer preview crash.

/unnamed : rx.form.field(...) with NO name= and an rx.form.message child
           -> @radix-ui/react-form throws "`FormMessage` must be used within
              `FormField` or specify the `name` prop" and reflex's error boundary
              replaces the whole page.
/named   : the identical tree with name= on the field -> renders fine.
"""

import reflex as rx


class S(rx.State):
    force: bool = False

    @rx.event
    def submit(self, data: dict):
        self.force = not data.get("who")


def tree(with_name: bool) -> rx.Component:
    field_kwargs = {"name": "who"} if with_name else {}
    return rx.form(
        rx.form.field(
            rx.card(
                rx.text("Who are you?"),
                rx.input(placeholder="name", name="who"),
                rx.form.message(
                    "This field is required.",
                    match="valueMissing",
                    force_match=S.force,
                    color=rx.color("tomato", 10),
                ),
            ),
            **field_kwargs,
        ),
        rx.button("Submit", type="submit"),
        on_submit=S.submit,
    )


@rx.page(route="/unnamed")
def unnamed() -> rx.Component:
    return rx.vstack(rx.heading("unnamed", id="hd"), tree(False))


@rx.page(route="/named")
def named() -> rx.Component:
    return rx.vstack(rx.heading("named", id="hd"), tree(True))


app = rx.App()
