# pyright: reportDeprecated=true
"""APIs new or deprecated in 0.10.1a1: expected to fail on 0.10.0 (not a regression there)."""

from typing import assert_type, reveal_type

import reflex as rx
from reflex_base.constants import Hooks
from reflex_base.vars.base import VarData


class FormState(rx.State):
    toppings: list[str] = []
    last: str = ""

    @rx.event
    def set_toppings(self, value: list[str]):
        self.toppings = value

    # rx.form.FormData[str, str] as a handler annotation (#7386 stub-as-class).
    @rx.event
    def handle_submit(self, form_data: rx.form.FormData[str, str]):
        self.toppings = form_data.getlist("topping")
        self.last = form_data.get("name", "")
        for key, value in form_data.items():
            assert_type(key, str)
            assert_type(value, str)


_form = rx.form(
    rx.checkbox_group.root(
        rx.checkbox_group.item("Olives", value="olives"),
        rx.checkbox_group.item("Onions", value="onions"),
        name="topping",
        value=FormState.toppings,
        on_value_change=FormState.set_toppings,
    ),
    rx.checkbox_cards.root(
        rx.checkbox_cards.item(rx.text("X"), value="x", disabled=True),
        name="cards",
        default_value=["x"],
        disabled=False,
        required=False,
        orientation="horizontal",
        dir="ltr",
        loop=True,
    ),
    on_submit=FormState.handle_submit,
)
_form_as_component: rx.Component = _form
reveal_type(_form)
_fd: rx.form.FormData[str, str] = rx.form.FormData({"a": "b"})
assert_type(_fd.getlist("a"), list[str])
reveal_type(rx.form.FormData)
from reflex_base.utils.form import FormData as BaseFormData  # noqa: E402

_fd2: BaseFormData[str, str] = BaseFormData({"a": "b"})
assert_type(_fd2.getlist("a"), list[str])

# rx.input auto_complete takes the HTML string (#7418).
_inputs = rx.vstack(
    rx.input(auto_complete="off"),
    rx.input(auto_complete="email"),
    rx.input(auto_complete=FormState.last),
)

# rx.moment_provider and the new moment options (#7591).
_moment = rx.moment_provider(
    rx.moment("2024-03-14", utc=True, calendar=True, ago=True, element="span", fallback="?"),
    rx.moment("2024-03-14", from_="2024-03-10", to="2024-03-20"),
    rx.moment("2024-03-14", filters=[rx.Var("(c) => c")], renderers=[rx.Var("(p, d) => null")]),
    locale="fr",
    format="D MMM YYYY",
    timezone="Europe/Paris",
    pool=True,
    interval=1000,
)

# VarData(position=...) is deprecated: a checker running reportDeprecated should flag it.
_vd = VarData(position=Hooks.HookPosition.PRE_TRIGGER)
_pos = Hooks.HookPosition.PRE_TRIGGER
