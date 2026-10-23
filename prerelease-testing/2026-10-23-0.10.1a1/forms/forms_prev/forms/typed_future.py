"""TypedDict form data in a module using ``from __future__ import annotations``.

Exercises the reflex-base #7386 line: Required/NotRequired honored, including
inside Annotated, when annotations are strings. The NotRequired fields have NO
matching form control.
"""

from __future__ import annotations

import json
from typing import Annotated, Any, NotRequired, Required, TypedDict

import reflex as rx


class FutureForm(TypedDict, total=False):
    """A total=False TypedDict: fields are NotRequired unless marked Required."""

    title: Required[str]
    nickname: NotRequired[str]  # no control -> left out
    tags: Annotated[NotRequired[list[str]], "annotated-notrequired"]  # no control
    agree: Required[Annotated[bool, "a bool inside Annotated"]]  # checkbox id==name
    extras: Required[list[str] | None]  # unchecked checkbox -> None
    maybe_flag: Required[bool | None]  # unchecked switch -> None


class FutureState(rx.State):
    """State for the future-annotations page."""

    data_json: str = ""
    keys: list[str] = []
    submissions: int = 0

    @rx.event
    def handle_future(self, form_data: FutureForm):
        """Receive the TypedDict-coerced form data.

        Args:
            form_data: The coerced form data.
        """
        self.submissions += 1
        self.data_json = json.dumps(form_data, sort_keys=True)
        self.keys = sorted(form_data.keys())


def typed_future_page() -> rx.Component:
    """The page.

    Returns:
        The page component.
    """
    return rx.vstack(
        rx.heading("TypedDict + from __future__ import annotations"),
        rx.form(
            rx.input(name="title", placeholder="title", default_value="hello"),
            rx.checkbox("agree", id="agree", name="agree", default_checked=True),
            rx.checkbox("extras", name="extras", value="e1"),
            rx.switch(name="maybe_flag"),
            rx.button("Submit future", type="submit", id="future-submit"),
            on_submit=FutureState.handle_future,
        ),
        rx.text("submissions: ", FutureState.submissions, id="future-count"),
        rx.code(FutureState.data_json, id="future-json"),
        rx.text(FutureState.keys.join(","), id="future-keys"),
        rx.link("home", href="/"),
        spacing="3",
        padding="1em",
    )
