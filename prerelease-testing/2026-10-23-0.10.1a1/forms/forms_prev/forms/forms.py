"""Forms cluster test app for reflex 0.10.1a1 (no __future__ annotations here)."""

import json
from typing import Annotated, Any, NotRequired, Required, TypedDict

import reflex as rx

from .typed_future import typed_future_page


def _dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=repr)


# index page


class DictState(rx.State):
    """Untyped / dict handlers and a FormData handler on one page."""

    untyped_json: str = ""
    dict_json: str = ""
    fd_items: str = ""
    fd_getlist: str = ""
    fd_dict_json: str = ""
    display: dict[str, str] = {}
    chained: str = ""
    submit_count: int = 0

    @rx.event
    def handle_untyped(self, form_data):
        """No annotation at all."""
        self.submit_count += 1
        self.untyped_json = _dump(form_data)
        self.display = {k: str(v) for k, v in form_data.items()}
        yield DictState.after_submit(form_data)
        yield rx.toast(f"submitted {len(form_data)} keys", id="submitted-toast")

    @rx.event
    def after_submit(self, form_data: dict):
        """Chained handler receiving the same form data (dict annotation)."""
        self.chained = _dump(form_data)

    @rx.event
    def handle_dict(self, form_data: dict[str, Any]):
        """dict annotation keeps last value per name."""
        self.dict_json = _dump(form_data)

    @rx.event
    def handle_formdata(self, form_data: dict):
        """FormData keeps every value per name in submission order."""
        self.fd_items = _dump(list(form_data.items()))
        self.fd_getlist = _dump(form_data.get("hobby"))
        self.fd_dict_json = _dump(dict(form_data))
        yield DictState.after_formdata(form_data)

    @rx.event
    def after_formdata(self, form_data: dict):
        """A FormData passed on to a dict-annotated handler."""
        self.chained = _dump(form_data)


def index() -> rx.Component:
    """Index page with three forms."""
    return rx.vstack(
        rx.heading("forms cluster: dict / untyped / FormData"),
        rx.form(
            rx.input(name="first", placeholder="first", default_value="Ann"),
            rx.input(name="second", placeholder="second (Enter submits)"),
            rx.checkbox("remember", id="remember", name="remember"),  # id == name
            rx.switch(name="dark", id="dark"),  # id == name, unchecked
            rx.checkbox("hobby a", name="hobby", value="a", default_checked=True),
            rx.checkbox("hobby b", name="hobby", value="b", default_checked=True),
            rx.checkbox("hobby c", name="hobby", value="c"),
            rx.select(["x", "y", "z"], name="pick", default_value="y"),
            rx.text_area(name="notes", default_value="line1\nline2"),
            rx.slider(name="range", default_value=[20, 60], id="range-slider"),
            rx.radio_group(["r1", "r2"], name="radio", default_value="r2"),
            rx.checkbox_group.root(
                rx.checkbox_group.item("g1", value="g1"),
                rx.checkbox_group.item("g2", value="g2"),
                rx.checkbox_group.item("g3", value="g3"),
                name="group",
                default_value=["g1", "g3"],
            ),
            rx.button("Submit untyped", type="submit", id="untyped-submit"),
            on_submit=DictState.handle_untyped,
            reset_on_submit=True,
            id="untyped-form",
        ),
        rx.text("count: ", DictState.submit_count, id="untyped-count"),
        rx.code(DictState.untyped_json, id="untyped-json"),
        rx.code(DictState.chained, id="chained-json"),
        rx.vstack(
            rx.foreach(
                DictState.display,
                lambda kv: rx.text(kv[0], "=", kv[1], class_name="display-item"),
            ),
            id="display",
        ),
        rx.divider(),
        rx.form(
            rx.input(name="hobby", default_value="h1"),
            rx.input(name="hobby", default_value="h2"),
            rx.input(name="hobby", default_value="h3"),
            rx.input(name="solo", default_value="only"),
            rx.button("Submit dict", type="submit", id="dict-submit"),
            on_submit=DictState.handle_dict,
        ),
        rx.code(DictState.dict_json, id="dict-json"),
        rx.divider(),
        rx.form(
            rx.input(name="hobby", default_value="h1"),
            rx.input(name="hobby", default_value="h2"),
            rx.input(name="hobby", default_value="h3"),
            rx.input(name="solo", default_value="only"),
            rx.slider(name="range", default_value=[1, 9]),
            rx.button("Submit FormData", type="submit", id="fd-submit"),
            on_submit=DictState.handle_formdata,
        ),
        rx.code(DictState.fd_items, id="fd-items"),
        rx.code(DictState.fd_getlist, id="fd-getlist"),
        rx.code(DictState.fd_dict_json, id="fd-dict"),
        rx.hstack(
            rx.link("typed", href="/typed"),
            rx.link("future", href="/future"),
            rx.link("deprecated", href="/deprecated"),
            rx.link("controlled", href="/controlled"),
            rx.link("cs", href="/cs"),
        ),
        spacing="3",
        padding="1em",
    )


# typed page


class TypedForm(TypedDict):
    """Total TypedDict with mixed Required/NotRequired."""

    name: str
    subscribe: bool  # checkbox id == name, may be unchecked -> False
    toggled: bool  # switch
    hobby: list[str]  # several checkboxes sharing a name
    color: Annotated[list[str], "checkbox_group"]  # checkbox_group name=color
    range: list[str]  # two-thumb slider submits range[]
    size: str  # radio_group
    bio: NotRequired[str]  # text_area, NotRequired but present
    missing_opt_list: NotRequired[list[str]]  # no control, left out
    opt_list: list[str] | None  # unchecked checkbox -> None (no control at all is a compile error)
    opt_flag: bool | None  # unchecked switch -> None
    strflag: Annotated[bool, "from select false-like string"]  # select with "false"/"true"
    controlled: NotRequired[str]  # 0.10.0 cannot see a controlled input name: NotRequired so it compiles
    foreach_val: list[str]  # rx.foreach generated inputs
    hidden_req: Required[str]  # inside rx.cond: hidden by default!


class TypedState(rx.State):
    """State for the typed page."""

    typed_json: str = ""
    type_map: str = ""
    error: str = ""
    controlled_value: str = "ctrl"
    labels: list[str] = ["f1", "f2", "f3"]
    show_hidden: bool = False

    @rx.event
    def set_controlled(self, v: str):
        self.controlled_value = v

    @rx.event
    def toggle_hidden(self):
        self.show_hidden = not self.show_hidden

    @rx.event
    def handle_typed(self, form_data: TypedForm):
        """Receive the TypedDict coerced form data."""
        self.typed_json = _dump(form_data)
        self.type_map = _dump({k: type(v).__name__ for k, v in form_data.items()})
        try:
            _ = form_data["hidden_req"]
            self.error = "hidden_req present"
        except KeyError as e:
            self.error = f"KeyError {e}"


def typed_page() -> rx.Component:
    """Page with a TypedDict handler."""
    return rx.vstack(
        rx.heading("TypedDict (no future annotations)"),
        rx.form(
            rx.input(name="name", default_value="Bob"),
            rx.checkbox("subscribe", id="subscribe", name="subscribe"),
            rx.switch(name="toggled", id="toggled", default_checked=True),
            rx.checkbox("h1", name="hobby", value="h1", default_checked=True),
            rx.checkbox("h2", name="hobby", value="h2"),
            rx.checkbox("h3", name="hobby", value="h3", default_checked=True),
            rx.checkbox_group.root(
                rx.checkbox_group.item("red", value="red"),
                rx.checkbox_group.item("blue", value="blue"),
                name="color",
                default_value=["blue"],
            ),
            rx.slider(name="range", default_value=[10, 30]),
            rx.checkbox("opt_list (unchecked)", name="opt_list", value="ol"),
            rx.switch(name="opt_flag"),
            rx.radio_group(["s", "m", "l"], name="size", default_value="m"),
            rx.text_area(name="bio", default_value="bio text"),
            rx.select(["true", "false", "off", "0", "yes"], name="strflag", default_value="false"),
            rx.input(
                name="controlled",
                value=TypedState.controlled_value,
                on_change=TypedState.set_controlled,
                id="controlled-input",
            ),
            rx.foreach(
                TypedState.labels,
                lambda label: rx.input(name="foreach_val", default_value=label),
            ),
            rx.cond(
                TypedState.show_hidden,
                rx.input(name="hidden_req", default_value="now visible"),
            ),
            rx.button("Submit typed", type="submit", id="typed-submit"),
            on_submit=TypedState.handle_typed,
        ),
        rx.button("toggle hidden", on_click=TypedState.toggle_hidden, id="toggle-hidden"),
        rx.code(TypedState.typed_json, id="typed-json"),
        rx.code(TypedState.type_map, id="typed-types"),
        rx.text(TypedState.error, id="typed-error"),
        rx.link("home", href="/"),
        spacing="3",
        padding="1em",
    )


# deprecated id page


class DeprecatedState(rx.State):
    """Form data from id-only / id != name / id == name controls."""

    dep_json: str = ""

    @rx.event
    def handle_dep(self, form_data: dict):
        self.dep_json = _dump(form_data)


def deprecated_page() -> rx.Component:
    """Controls with ids but not names -> compile-time deprecation warnings."""
    return rx.vstack(
        rx.heading("id-only / id != name / checkbox id == name"),
        rx.form(
            rx.input(id="only_id", default_value="idval"),  # id only -> warning
            rx.input(id="the_id", name="the_name", default_value="both"),  # id != name
            rx.checkbox("cb", id="cb", name="cb", default_checked=True),  # id == name
            rx.switch(id="sw", name="sw"),  # id == name, unchecked
            rx.checkbox("cbid", id="cbid_only", default_checked=True),  # id only checkbox
            rx.text_area(id="ta_only", default_value="ta"),  # id only textarea
            rx.select(["a", "b"], id="sel_only", default_value="b"),  # id only select
            rx.input(id="disabled_id", default_value="d", disabled=True),  # no warning
            rx.input(type="submit", id="sub_id", value="go"),  # valueless type
            rx.slider(id="slider_id", default_value=[5]),  # id only slider
            rx.button("Submit dep", type="submit", id="dep-submit"),
            on_submit=DeprecatedState.handle_dep,
        ),
        rx.code(DeprecatedState.dep_json, id="dep-json"),
        rx.link("home", href="/"),
        spacing="3",
        padding="1em",
    )


# controlled page


class ControlledForm(TypedDict):
    cg: list[str]
    cc: NotRequired[list[str]]  # 0.10.0 checkbox_cards has no name prop
    rc: str
    email: str
    off_field: str
    on_field: str
    bool_false: str


class ControlledState(rx.State):
    """Controlled checkbox_group / checkbox_cards with on_value_change."""

    cg_value: list[str] = ["b"]
    cc_value: list[str] = ["y"]
    cg_changes: int = 0
    cc_changes: int = 0
    ctrl_json: str = ""

    @rx.event
    def set_cg(self, v: list[str]):
        self.cg_changes += 1
        self.cg_value = v

    @rx.event
    def set_cc(self, v: list[str]):
        self.cc_changes += 1
        self.cc_value = v

    @rx.event
    def handle_ctrl(self, form_data: ControlledForm):
        self.ctrl_json = _dump(form_data)


def controlled_page() -> rx.Component:
    return rx.vstack(
        rx.heading("controlled checkbox_group / checkbox_cards / auto_complete"),
        rx.form(
            rx.checkbox_group.root(
                rx.checkbox_group.item("a", value="a"),
                rx.checkbox_group.item("b", value="b"),
                rx.checkbox_group.item("c", value="c"),
                name="cg",
                default_value=ControlledState.cg_value,
                id="cg-root",
            ),
            rx.checkbox_cards.root(
                rx.checkbox_cards.item("x", value="x"),
                rx.checkbox_cards.item("y", value="y"),
                default_value=ControlledState.cc_value,
                id="cc-root",
            ),
            rx.radio_cards.root(
                rx.radio_cards.item("p", value="p"),
                rx.radio_cards.item("q", value="q"),
                name="rc",
                default_value="q",
            ),
            rx.input(name="email", default_value="a@b.c", id="ac-email"),  # str auto_complete raises TypeError on 0.10.0
            rx.input(name="off_field", id="ac-off"),
            rx.input(name="on_field", auto_complete=True, id="ac-true"),
            rx.input(name="bool_false", auto_complete=False, id="ac-false"),
            rx.button("Submit ctrl", type="submit", id="ctrl-submit"),
            on_submit=ControlledState.handle_ctrl,
        ),
        rx.text("cg=", ControlledState.cg_value.join(","), " changes=", ControlledState.cg_changes, id="cg-state"),
        rx.text("cc=", ControlledState.cc_value.join(","), " changes=", ControlledState.cc_changes, id="cc-state"),
        rx.code(ControlledState.ctrl_json, id="ctrl-json"),
        rx.link("home", href="/"),
        spacing="3",
        padding="1em",
    )


# ComponentState page


class CSForm(TypedDict):
    item: str
    checks: list[str]
    flag: bool


class CounterForm(rx.ComponentState):
    """A form inside a ComponentState, two instances on the page."""

    last: str = ""
    n: int = 0

    @rx.event
    def submit(self, form_data: CSForm):
        self.n += 1
        self.last = _dump(form_data)

    @classmethod
    def get_component(cls, label: str, **props) -> rx.Component:
        return rx.vstack(
            rx.form(
                rx.input(name="item", default_value=label),
                rx.checkbox("c1", name="checks", value="c1", default_checked=True),
                rx.checkbox("c2", name="checks", value="c2"),
                rx.switch(name="flag", id=f"flag-{label}"),
                rx.button("Submit " + label, type="submit", class_name="cs-submit"),
                on_submit=cls.submit,
            ),
            rx.text("n=", cls.n, class_name="cs-n"),
            rx.code(cls.last, class_name="cs-last"),
            **props,
        )


counter_form = CounterForm.create


def cs_page() -> rx.Component:
    return rx.vstack(
        rx.heading("ComponentState forms"),
        counter_form("alpha", id="cs-alpha"),
        counter_form("beta", id="cs-beta"),
        rx.link("home", href="/"),
        spacing="3",
        padding="1em",
    )


app = rx.App()
app.add_page(index, route="/")
app.add_page(typed_page, route="/typed")
app.add_page(typed_future_page, route="/future")
app.add_page(deprecated_page, route="/deprecated")
app.add_page(controlled_page, route="/controlled")
app.add_page(cs_page, route="/cs")
