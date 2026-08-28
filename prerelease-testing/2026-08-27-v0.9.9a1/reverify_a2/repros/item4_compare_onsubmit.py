"""Compare on_submit warning behavior: plain dict[str, str] vs Pair[str, str]."""

from typing import TypeVar

from typing_extensions import TypeAliasType

import reflex as rx

_K = TypeVar("_K")
_V = TypeVar("_V")
Pair = TypeAliasType("Pair", dict[_K, _V], type_params=(_K, _V))  # pyright: ignore[reportGeneralTypeIssues]


class S(rx.State):
    key: str = ""

    @rx.event
    def submit_plain(self, form_data: dict[str, str]):
        self.key = str(form_data)

    @rx.event
    def submit_alias(self, form_data: Pair[str, str]):  # pyright: ignore[reportInvalidTypeForm]
        self.key = str(form_data)


print("--- plain dict[str, str] ---")
rx.form(rx.input(name="x"), on_submit=S.submit_plain).render()
print("--- alias Pair[str, str] ---")
rx.form(rx.input(name="x"), on_submit=S.submit_alias).render()
print("done")
