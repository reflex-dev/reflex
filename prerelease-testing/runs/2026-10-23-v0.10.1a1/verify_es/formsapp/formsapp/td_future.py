"""TypedDict handlers under ``from __future__ import annotations`` (NotRequired / Required as strings)."""

from __future__ import annotations

from typing import Annotated, TypedDict

import reflex as rx
from typing_extensions import NotRequired, Required

from .formsapp import State


class FuturePrefs(TypedDict):
    name: str
    toppings: list[str]
    agree: bool
    maybe: bool | None
    note: NotRequired[str]
    nr_list: NotRequired[list[str]]
    nr_bool: NotRequired[bool]
    nr_opt: NotRequired[bool | None]
    req_ann: Required[Annotated[str, "x"]]
    nr_ann: Annotated[NotRequired[str], "y"]


class FutureState(State):
    @rx.event
    def typed_future(self, form_data: FuturePrefs):
        self._record("future", form_data, {"py_types": {k: type(v).__name__ for k, v in form_data.items()}})

    @rx.event
    def fd_future(self, form_data: rx.form.FormData[str, str]):
        self._record("future_fd", form_data, {"getlist": form_data.getlist("rep")})
