"""A sign-up form with validation on blur and on submit."""

from typing import Any

import reflex as rx

PLANS = ("hobby", "team", "enterprise")


def is_email(value: str) -> bool:
    """Tell whether a value looks like an email address.

    Args:
        value: The value.

    Returns:
        Whether it has an ``@`` followed by a domain with a dot.
    """
    return "@" in value and "." in value.rpartition("@")[2]


def check_signup(form: dict[str, str]) -> dict[str, str]:
    """Validate a sign-up.

    Args:
        form: The submitted fields.

    Returns:
        The errors per field; empty when the sign-up is valid.
    """
    errors: dict[str, str] = {}
    if len(form.get("username", "").strip()) < 3:
        errors["username"] = "At least 3 characters."
    if not is_email(form.get("email", "")):
        errors["email"] = "Not an email address."
    age = form.get("age", "")
    if not age.isdigit() or not 13 <= int(age) <= 120:
        errors["age"] = "An age from 13 to 120."
    if form.get("plan") not in PLANS:
        errors["plan"] = "Pick a plan."
    if form.get("terms") != "on":
        errors["terms"] = "Accept the terms."
    return errors


class FormState(rx.State):
    """The form's errors and the accepted sign-ups."""

    errors: rx.Field[dict[str, str]] = rx.field(default_factory=dict)
    plan: str = "hobby"
    signups: list[dict[str, str]] = []

    @rx.var
    def signup_count(self) -> int:
        """Count the accepted sign-ups.

        Returns:
            The number of sign-ups.
        """
        return len(self.signups)

    @rx.event
    def set_plan(self, value: str):
        """Choose a plan.

        Args:
            value: The plan.
        """
        self.plan = value

    @rx.event
    def check_email(self, value: str):
        """Validate the email field as it loses focus.

        Args:
            value: The field's value.
        """
        if is_email(value):
            self.errors.pop("email", None)
        else:
            self.errors["email"] = "Not an email address."

    @rx.event
    def submit(self, form_data: dict[str, Any]):
        """Validate and accept a sign-up.

        Args:
            form_data: The submitted fields.

        Returns:
            A toast saying what happened.
        """
        self.errors = check_signup({**form_data, "plan": self.plan})
        if self.errors:
            return rx.toast.error("The form has errors.")
        self.signups.append({
            "username": form_data["username"],
            "email": form_data["email"],
            "plan": self.plan,
        })
        return rx.toast.success(f"Welcome, {form_data['username']}!")

    @rx.event
    def reset_signups(self):
        """Forget the sign-ups and the errors."""
        self.signups = []
        self.errors = {}
