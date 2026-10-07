"""Minimal #7227 repro: IDs on the form, a wrapper and a button must not be submitted."""

import reflex as rx


class FormState(rx.State):
    """Holds the last submitted form data."""

    form_data: rx.Field[dict] = rx.field(default_factory=dict)

    @rx.event
    def form_submit(self, data: dict):
        self.form_data = data


def index() -> rx.Component:
    return rx.vstack(
        rx.form(
            rx.vstack(
                rx.input(id="name_input", default_value="foo"),
                rx.input(id="empty_input"),
                rx.checkbox(id="bool_input", default_checked=True),
                rx.button("Submit", type="submit", id="submit"),
                id="form_content_wrapper",
            ),
            on_submit=FormState.form_submit,
            id="form_id",
        ),
        rx.text(FormState.form_data.to_string(), id="form-data"),
    )


app = rx.App()
app.add_page(index)
