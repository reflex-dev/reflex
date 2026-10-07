"""Separate select identity cases from the large form fixture."""

import json

import reflex as rx


class SelectState(rx.State):
    """Store exact form payloads."""

    payload: str = ""
    submissions: int = 0

    @rx.event
    def submit(self, data: dict[str, str]):
        """Record one submission.

        Args:
            data: Values collected by the form.
        """
        self.payload = json.dumps(data, sort_keys=True)
        self.submissions += 1


def select_matrix() -> rx.Component:
    """Render the id-only, name-only and combined select cases.

    Returns:
        The independent form page.
    """
    return rx.vstack(
        rx.heading("Select identity matrix"),
        rx.form(
            rx.vstack(
                rx.select(["a", "b"], id="select_id"),
                rx.select(["a", "b"], name="select_name"),
                rx.select(["a", "b"], id="select_both", name="select_both_name"),
                rx.button("Submit matrix", type="submit", id="submit_matrix"),
            ),
            on_submit=SelectState.submit,
        ),
        rx.text(SelectState.payload, id="select_payload"),
        rx.text(SelectState.submissions, id="select_submissions"),
        padding="2em",
    )
