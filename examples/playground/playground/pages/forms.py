"""The forms page: a sign-up form validated on blur and on submit."""

import reflex as rx

from playground.layout import layout
from playground.states.forms import PLANS, FormState


def error_text(field: str) -> rx.Component:
    """Render a field's error, if it has one.

    Args:
        field: The field's name.

    Returns:
        The error, in red.
    """
    return rx.cond(
        FormState.errors.contains(field),
        rx.text(
            FormState.errors[field],
            color_scheme="red",
            size="1",
            id=f"forms-error-{field}",
        ),
    )


def labelled(label: str, field: str, control: rx.Component) -> rx.Component:
    """Stack a label, a control and the field's error.

    Args:
        label: The label.
        field: The field's name.
        control: The input.

    Returns:
        The stack.
    """
    return rx.vstack(
        rx.text(label, size="2", weight="medium"),
        control,
        error_text(field),
        spacing="1",
        width="100%",
    )


def signup_row(signup: rx.vars.ObjectVar[dict[str, str]]) -> rx.Component:
    """Render one accepted sign-up.

    Args:
        signup: The sign-up.

    Returns:
        A table row.
    """
    return rx.table.row(
        rx.table.cell(signup["username"]),
        rx.table.cell(signup["email"]),
        rx.table.cell(signup["plan"]),
    )


def forms() -> rx.Component:
    """Render the forms page.

    Returns:
        The form and the accepted sign-ups.
    """
    return layout(
        rx.vstack(
            rx.heading("Forms"),
            rx.form(
                rx.vstack(
                    labelled(
                        "Username",
                        "username",
                        rx.input(name="username", id="forms-username"),
                    ),
                    labelled(
                        "Email",
                        "email",
                        rx.input(
                            name="email",
                            type="email",
                            on_blur=FormState.check_email,
                            id="forms-email",
                        ),
                    ),
                    labelled(
                        "Age",
                        "age",
                        rx.input(name="age", type="number", id="forms-age"),
                    ),
                    labelled(
                        "Plan",
                        "plan",
                        rx.radio_group(
                            list(PLANS),
                            value=FormState.plan,
                            on_change=FormState.set_plan,
                            direction="row",
                            id="forms-plan",
                        ),
                    ),
                    labelled(
                        "Terms",
                        "terms",
                        rx.checkbox(
                            "I accept the terms", name="terms", id="forms-terms"
                        ),
                    ),
                    rx.hstack(
                        rx.button("Sign up", type="submit", id="forms-submit"),
                        rx.button(
                            "Reset",
                            type="reset",
                            variant="soft",
                            color_scheme="gray",
                            id="forms-reset",
                        ),
                    ),
                    width="100%",
                ),
                on_submit=FormState.submit,
                reset_on_submit=True,
                id="forms-signup",
                width="100%",
                max_width="28rem",
            ),
            rx.heading(FormState.signup_count, " sign-ups", size="3", id="forms-count"),
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Username"),
                        rx.table.column_header_cell("Email"),
                        rx.table.column_header_cell("Plan"),
                    )
                ),
                rx.table.body(rx.foreach(FormState.signups, signup_row)),
                id="forms-signups",
            ),
            rx.button(
                "Forget sign-ups",
                on_click=FormState.reset_signups,
                variant="soft",
                id="forms-forget",
            ),
            width="100%",
        )
    )
