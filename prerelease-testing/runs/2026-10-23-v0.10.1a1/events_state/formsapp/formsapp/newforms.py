"""The 0.10.1a1 form API: rx.form.FormData handlers and TypedDict coercion (needs FORMS_NEW=1)."""

import json
from typing import Annotated, Any, Generic, Literal, TypedDict, TypeVar

import reflex as rx
from typing_extensions import NotRequired, Required
from typing_extensions import TypedDict as TETypedDict

from .formsapp import State, wrap
from . import td_future


class Prefs(TypedDict):
    name: str
    toppings: list[str]
    agree: bool
    sw: bool
    maybe: bool | None
    opt_list: list[str] | None
    note: NotRequired[str]
    nr_list: NotRequired[list[str]]
    nr_bool: NotRequired[bool]
    range: list[str]
    ann: Annotated[str, "meta"]
    req_ann: Required[Annotated[str, "x"]]
    count: int
    hidden_false: bool
    sel_bool: bool
    lit: Literal["x", "y"]
    cg: list[str]


class Tags(TypedDict):
    tags: list[str]
    single: list[str]


T = TypeVar("T")


class GBase(TETypedDict, Generic[T]):
    v: T


class GList(GBase[list[str]]):
    other: bool


class NewState(State):
    fd_results: dict[str, str] = {}
    cg_value: list[str] = ["c2"]

    @rx.event
    def set_cg_value(self, v: list[str]):
        self.cg_value = v

    @rx.event
    def formdata(self, form_data: rx.form.FormData[str, str]):
        self._record(
            "formdata",
            form_data,
            {
                "getlist_topping": form_data.getlist("topping"),
                "getAll_range": form_data.getAll("range[]"),
                "index_topping": form_data.get("topping"),
                "as_dict": {k: v for k, v in form_data.items()},
                "len": len(form_data),
                "keys": list(form_data),
            },
        )

    @rx.event
    def formdata_optional(self, form_data: rx.form.FormData[str, str] | None):
        self._record("formdata_optional", form_data)

    @rx.event
    def formdata_passon(self, form_data: rx.form.FormData[str, str]):
        self._record("passon_fd", form_data)
        return [NewState.passon_dict(form_data), NewState.passon_td(form_data), NewState.passon_fd2(form_data)]

    @rx.event
    def passon_dict(self, form_data: dict):
        self._record("passon_dict", form_data)

    @rx.event
    def passon_td(self, form_data: Tags):
        self._record("passon_td", form_data)

    @rx.event
    def passon_fd2(self, form_data: rx.form.FormData[str, str]):
        self._record("passon_fd2", form_data)

    @rx.event
    def typed(self, form_data: Prefs):
        self._record("typed", form_data, {"py_types": {k: type(v).__name__ for k, v in form_data.items()}})

    @rx.event
    def typed_tags(self, form_data: Tags):
        self._record("typed_tags", form_data)

    @rx.event
    def typed_generic(self, form_data: GList):
        self._record("typed_generic", form_data, {"py_types": {k: type(v).__name__ for k, v in form_data.items()}})

    @rx.event
    def typed_dynamic(self, form_data: Tags):
        self._record("typed_dynamic", form_data)


def new_page() -> rx.Component:
    return rx.vstack(
        rx.text("seq: ", rx.el.span(State.seq, id="seq")),
        rx.el.pre(State.results_json, id="results", style={"white-space": "pre-wrap"}),
        # n01 FormData handler
        wrap(
            "formdata",
            rx.el.input(type="checkbox", name="topping", value="cheese"),
            rx.el.input(type="checkbox", name="topping", value="olives"),
            rx.el.input(type="checkbox", name="topping", value="ham"),
            rx.slider(default_value=[20, 80], name="range"),
            rx.input(name="a", default_value="A"),
            rx.input(id="idonly", default_value="IDONLY"),
            rx.checkbox("cbboth", id="cbboth", name="cbboth"),
            rx.checkbox_group.root(rx.checkbox_group.item("c1", value="c1"), rx.checkbox_group.item("c2", value="c2"), rx.checkbox_group.item("c3", value="c3"), id="cg", name="cg"),
            rx.input(name="rep", default_value="rep1"),
            rx.input(name="rep", default_value="rep2"),
            on_submit=NewState.formdata,
        ),
        wrap(
            "formdata_optional",
            rx.input(name="rep", default_value="rep1"),
            rx.input(name="rep", default_value="rep2"),
            on_submit=NewState.formdata_optional,
        ),
        wrap(
            "passon",
            rx.input(name="tags", default_value="t1"),
            rx.input(name="tags", default_value="t2"),
            rx.input(name="single[]", default_value="s1"),
            on_submit=NewState.formdata_passon,
        ),
        # n02 TypedDict with every coercion kind
        wrap(
            "typed",
            rx.input(name="name", default_value="Ann"),
            rx.el.input(type="checkbox", name="toppings", value="cheese"),
            rx.el.input(type="checkbox", name="toppings", value="olives"),
            rx.checkbox("agree", name="agree"),
            rx.switch(name="sw"),
            rx.switch(name="maybe"),
            rx.el.input(type="checkbox", name="opt_list", value="ol1"),
            rx.input(name="note"),
            rx.el.input(type="checkbox", name="nr_list", value="nr1"),
            rx.checkbox("nr_bool", name="nr_bool"),
            rx.slider(default_value=[20, 80], name="range"),
            rx.input(name="ann", default_value="ANN"),
            rx.input(name="req_ann", default_value="REQ"),
            rx.input(name="count", type="number", default_value="7"),
            rx.el.input(type="hidden", name="hidden_false", value="false"),
            rx.el.select(
                rx.el.option("yes", value="yes"),
                rx.el.option("no", value="no"),
                name="sel_bool",
                default_value="no",
            ),
            rx.el.input(type="hidden", name="lit", value="zzz"),
            rx.checkbox_group.root(rx.checkbox_group.item("c1", value="c1"), rx.checkbox_group.item("c2", value="c2"), rx.checkbox_group.item("c3", value="c3"), name="cg", value=NewState.cg_value, on_value_change=NewState.set_cg_value),
            on_submit=NewState.typed,
        ),
        # n03 list field filled by name[] controls
        wrap(
            "typed_tags",
            rx.input(name="tags[]", default_value="t1"),
            rx.input(name="tags[]", default_value="t2"),
            rx.input(name="single[]", default_value="s1"),
            on_submit=NewState.typed_tags,
        ),
        # n04 generic TypedDict
        wrap(
            "typed_generic",
            rx.el.input(type="checkbox", name="v", value="v1", default_checked=True),
            rx.el.input(type="checkbox", name="v", value="v2", default_checked=True),
            rx.checkbox("other", name="other"),
            on_submit=NewState.typed_generic,
        ),
        # n05 TypedDict + dynamic names (validation skipped) and nothing matching at runtime
        wrap(
            "typed_dynamic",
            rx.input(name=State.dyn_name, default_value="dyn"),
            on_submit=NewState.typed_dynamic,
        ),
        # n06 controlled checkbox_group (#7345) in a dict form
        wrap(
            "cg_controlled",
            rx.checkbox_group.root(rx.checkbox_group.item("c1", value="c1"), rx.checkbox_group.item("c2", value="c2"), rx.checkbox_group.item("c3", value="c3"), name="cg", value=NewState.cg_value, on_value_change=NewState.set_cg_value),
            rx.text("cg_value=", NewState.cg_value.to_string(), id="cg_value"),
            on_submit=State.store("cg_controlled"),
        ),
    )


def future_page() -> rx.Component:
    return rx.vstack(
        rx.text("seq: ", rx.el.span(State.seq, id="seq")),
        rx.el.pre(State.results_json, id="results", style={"white-space": "pre-wrap"}),
        wrap(
            "future",
            rx.input(name="name", default_value="Fut"),
            rx.el.input(type="checkbox", name="toppings", value="x"),
            rx.checkbox("agree", name="agree"),
            rx.switch(name="maybe"),
            rx.input(name="req_ann", default_value="RA"),
            on_submit=td_future.FutureState.typed_future,
        ),
        wrap(
            "future_fd",
            rx.input(name="rep", default_value="r1"),
            rx.input(name="rep", default_value="r2"),
            on_submit=td_future.FutureState.fd_future,
        ),
    )
