"""Which `form_data` annotations does rx.form(on_submit=...) accept at compile time?

Run: cd $W && EXPECT_VENV=<venv> $SB/envs/<venv>/bin/python -I probe_form_annotations.py
"""

import dataclasses
import os
from collections.abc import Mapping, MutableMapping
from typing import Any, Optional, TypedDict

import pydantic
import reflex as rx

assert f"/envs/{os.environ.get('EXPECT_VENV', 'new')}/" in rx.__file__, rx.__file__


@dataclasses.dataclass
class DC:
    a: str = ""


class Pyd(pydantic.BaseModel):
    a: str = ""


class TD(TypedDict, total=False):
    a: str


class S(rx.State):
    @rx.event
    def h_dataclass(self, form_data: DC): ...
    @rx.event
    def h_pydantic(self, form_data: Pyd): ...
    @rx.event
    def h_mapping(self, form_data: Mapping[str, Any]): ...
    @rx.event
    def h_mutmapping(self, form_data: MutableMapping[str, Any]): ...
    @rx.event
    def h_optdict(self, form_data: dict | None): ...
    @rx.event
    def h_optional_dict(self, form_data: Optional[dict]): ...  # noqa: UP045
    @rx.event
    def h_any(self, form_data: Any): ...
    @rx.event
    def h_dict_str_str(self, form_data: dict[str, str]): ...
    @rx.event
    def h_dict_str_any(self, form_data: dict[str, Any]): ...
    @rx.event
    def h_dict_bare(self, form_data: dict): ...
    @rx.event
    def h_td_total_false(self, form_data: TD): ...
    @rx.event
    def h_none(self, form_data): ...
    @rx.event
    def h_str(self, form_data: str): ...
    @rx.event
    def h_object(self, form_data: object): ...


for name in [n for n in dir(S) if n.startswith("h_")]:
    try:
        rx.form(rx.input(name="a"), on_submit=getattr(S, name))
        print(f"OK   {name}")
    except Exception as e:  # noqa: BLE001
        print(f"EXC  {name}: {type(e).__name__}: {str(e).splitlines()[0][:170]}")
