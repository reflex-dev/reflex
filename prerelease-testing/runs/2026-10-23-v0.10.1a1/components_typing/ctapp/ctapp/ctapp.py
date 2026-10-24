"""components_typing QA app: radix / moment / data_editor / lucide / code changes in 0.10.1a1.

Runs on 0.10.1a1 (EXPECT_VENV=new) and, with the ``NEW`` guards, on 0.10.0
(EXPECT_VENV=components_typing-prev) so every browser check has a baseline.
"""

import json
import os
from typing import Any

import reflex as rx
from reflex_base.utils.imports import ImportVar
from reflex_components_lucide.icon import LUCIDE_LIBRARY
from reflex_components_radix.primitives.progress import progress as primitive_progress

assert f"/envs/{os.environ.get('EXPECT_VENV', 'new')}/" in rx.__file__, rx.__file__

# 0.10.1a1 adds rx.moment_provider; everything new is guarded on it.
NEW = hasattr(rx, "moment_provider")

PAGES = [
    "cbg",
    "radio",
    "radio_aschild",
    "input",
    "progress",
    "accordion",
    "dialog",
    "slider",
    "rform",
    "moment",
    "de",
    "icons",
    "code",
]

D = "2024-03-14T15:09:26"


def nav() -> rx.Component:
    return rx.hstack(
        rx.text(f"NEW={NEW}", id="is-new"),
        *[rx.link(p, href=f"/{p}", id=f"nav-{p}") for p in PAGES],
        spacing="3",
        wrap="wrap",
        id="nav",
    )


def index() -> rx.Component:
    return rx.vstack(nav(), rx.heading("components_typing", id="title"))


class CbgState(rx.State):
    group_value: list[str] = ["a"]
    cards_value: list[str] = []
    group_disabled: bool = False
    group_changes: int = 0
    cards_changes: int = 0
    last_group_payload: str = ""
    submitted: str = ""

    @rx.event
    def set_group(self, value: list[str]):
        self.group_value = value
        self.group_changes += 1
        self.last_group_payload = json.dumps(value)

    @rx.event
    def set_cards(self, value: list[str]):
        self.cards_value = value
        self.cards_changes += 1

    @rx.event
    def clear_all(self):
        self.group_value = []
        self.cards_value = []

    @rx.event
    def preset(self):
        self.group_value = ["a", "c"]
        self.cards_value = ["x", "z"]

    @rx.event
    def toggle_disabled(self):
        self.group_disabled = not self.group_disabled

    if NEW:

        @rx.event
        def on_submit(self, form_data: rx.form.FormData[str, str]):
            self.submitted = json.dumps({k: form_data.getlist(k) for k in form_data})

    else:

        @rx.event
        def on_submit(self, form_data: dict):
            self.submitted = json.dumps(form_data)


def cbg_page() -> rx.Component:
    group_items = [
        rx.checkbox_group.item("A", value="a"),
        rx.checkbox_group.item("B (disabled)", value="b", disabled=True),
        rx.checkbox_group.item("C", value="c"),
    ]
    card_items = [
        rx.checkbox_cards.item(rx.text("X"), value="x"),
        rx.checkbox_cards.item(rx.text("Y (disabled)"), value="y", disabled=True),
        rx.checkbox_cards.item(rx.text("Z"), value="z"),
    ]
    if NEW:
        group = rx.checkbox_group.root(
            *group_items,
            value=CbgState.group_value,
            on_value_change=CbgState.set_group,
            name="grp",
            disabled=CbgState.group_disabled,
            orientation="horizontal",
            loop=True,
            id="cg",
        )
        cards = rx.checkbox_cards.root(
            *card_items,
            value=CbgState.cards_value,
            on_value_change=CbgState.set_cards,
            name="cards",
            columns="3",
            id="cc",
        )
    else:
        group = rx.checkbox_group.root(
            *group_items, default_value=["a"], name="grp", id="cg"
        )
        cards = rx.checkbox_cards.root(
            *card_items, default_value=[], name="cards", columns="3", id="cc"
        )
    return rx.vstack(
        nav(),
        rx.form(
            group,
            cards,
            rx.checkbox_group.root(
                rx.checkbox_group.item("D1", value="d1"),
                rx.checkbox_group.item("D2", value="d2"),
                default_value=["d2"],
                name="dgrp",
                id="cg-default",
            ),
            rx.button("Submit", type="submit", id="cg-submit"),
            on_submit=CbgState.on_submit,
            id="cg-form",
        ),
        rx.text("group=", CbgState.group_value.join(","), id="group-value"),
        rx.text("cards=", CbgState.cards_value.join(","), id="cards-value"),
        rx.text("group_changes=", CbgState.group_changes, id="group-changes"),
        rx.text("cards_changes=", CbgState.cards_changes, id="cards-changes"),
        rx.text("payload=", CbgState.last_group_payload, id="group-payload"),
        rx.text("submitted=", CbgState.submitted, id="submitted"),
        rx.text("disabled=", CbgState.group_disabled.to_string(), id="group-disabled"),
        rx.hstack(
            rx.button("reset", on_click=CbgState.clear_all, id="cg-reset"),
            rx.button("preset", on_click=CbgState.preset, id="cg-preset"),
            rx.button(
                "toggle disabled", on_click=CbgState.toggle_disabled, id="cg-toggle"
            ),
        ),
    )


class RadioState(rx.State):
    rc_value: str = "1"

    @rx.event
    def set_rc(self, value: str):
        self.rc_value = value


def radio_items() -> list[rx.Component]:
    return [
        rx.radio_cards.item(rx.text("One"), value="1"),
        rx.radio_cards.item(rx.text("Two"), value="2"),
        rx.radio_cards.item(rx.text("Three"), value="3"),
    ]


def radio_page() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.radio_cards.root(
            *radio_items(),
            value=RadioState.rc_value,
            on_value_change=RadioState.set_rc,
            columns="3",
            id="rc",
        ),
        rx.text("rc=", RadioState.rc_value, id="rc-value"),
    )


def radio_aschild_page() -> rx.Component:
    # #7593: as_child was removed from radio_cards.root/item. Before, Radix got
    # asChild=true and the page crashed with several cards.
    return rx.vstack(
        nav(),
        rx.radio_cards.root(
            rx.radio_cards.item(rx.text("One"), value="1", as_child=True),
            rx.radio_cards.item(rx.text("Two"), value="2"),
            rx.radio_cards.item(rx.text("Three"), value="3"),
            default_value="1",
            columns="3",
            as_child=True,
            id="rc-aschild",
        ),
        rx.text("aschild page loaded", id="rc-aschild-ok"),
    )


class InputState(rx.State):
    ac_bool: bool = False
    ac_str: str = "email"
    typed: str = ""

    @rx.event
    def toggle_ac(self):
        self.ac_bool = not self.ac_bool

    @rx.event
    def set_typed(self, value: str):
        self.typed = value


def input_page() -> rx.Component:
    string_cases = (
        [
            rx.input(placeholder="off", auto_complete="off", id="ac-off"),
            rx.input(placeholder="email", auto_complete="email", id="ac-email"),
            rx.input(placeholder="strvar", auto_complete=InputState.ac_str, id="ac-strvar"),
            rx.input(
                placeholder="controlled",
                value=InputState.typed,
                on_change=InputState.set_typed,
                auto_complete="off",
                id="ac-controlled",
            ),
        ]
        if NEW
        else [rx.text("string auto_complete n/a on prev", id="ac-off")]
    )
    return rx.vstack(
        nav(),
        *string_cases,
        rx.input(placeholder="true", auto_complete=True, id="ac-true"),
        rx.input(placeholder="false", auto_complete=False, id="ac-false"),
        rx.input(placeholder="boolvar", auto_complete=InputState.ac_bool, id="ac-boolvar"),
        rx.input(placeholder="none", id="ac-none"),
        rx.el.input(placeholder="el", auto_complete="off", id="ac-el"),
        rx.button("toggle", on_click=InputState.toggle_ac, id="ac-toggle"),
        rx.text("typed=", InputState.typed, id="typed"),
        rx.text("ac_bool=", InputState.ac_bool.to_string(), id="ac-bool"),
    )


class ProgressState(rx.State):
    value: int = 25

    @rx.event
    def bump(self):
        self.value = (self.value + 25) % 125


def progress_page() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.progress(value=ProgressState.value, max=100, id="themes-progress"),
        primitive_progress(value=ProgressState.value, max=100, id="prim-progress"),
        primitive_progress(value=60, max=200, id="prim-progress-lit"),
        primitive_progress(id="prim-progress-default"),
        rx.button("bump", on_click=ProgressState.bump, id="bump"),
        rx.text("pv=", ProgressState.value, id="pv"),
        width="300px",
    )


def acc_items(prefix: str) -> list[rx.Component]:
    return [
        rx.accordion.item(
            header=f"{prefix} First", content=f"{prefix} first content", value="i1"
        ),
        rx.accordion.item(
            header=f"{prefix} Second", content=f"{prefix} second content", value="i2"
        ),
        rx.accordion.item(
            header=f"{prefix} Third", content=f"{prefix} third content", value="i3"
        ),
    ]


def accordion_page() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.accordion.root(
            *acc_items("M"), collapsible=True, type="multiple", width="300px", id="acc"
        ),
        rx.accordion.root(
            *acc_items("G"),
            variant="ghost",
            type="single",
            collapsible=True,
            width="300px",
            id="acc-ghost",
        ),
        rx.accordion.root(
            *acc_items("S"),
            variant="surface",
            type="single",
            default_value="i2",
            width="300px",
            id="acc-surface",
        ),
    )


class DialogState(rx.State):
    open: bool = False
    opens: int = 0

    @rx.event
    def set_open(self, value: bool):
        self.open = value
        if value:
            self.opens += 1


def dialog_page() -> rx.Component:
    nested = rx.dialog.root(
        rx.dialog.trigger(rx.button("Open nested", id="open-nested")),
        rx.dialog.content(
            rx.dialog.title("Nested"),
            rx.input(id="nested-input", placeholder="nested"),
            rx.dialog.close(rx.button("Close nested", id="close-nested")),
            id="nested-content",
        ),
    )
    return rx.vstack(
        nav(),
        rx.dialog.root(
            rx.dialog.trigger(rx.button("Open dialog", id="open-dialog")),
            rx.dialog.content(
                rx.dialog.title("Outer"),
                rx.dialog.description("outer description"),
                rx.input(id="outer-input", placeholder="outer"),
                rx.button("other", id="outer-btn"),
                nested,
                rx.dialog.close(rx.button("Close", id="close-dialog")),
                id="outer-content",
            ),
            open=DialogState.open,
            on_open_change=DialogState.set_open,
        ),
        rx.alert_dialog.root(
            rx.alert_dialog.trigger(rx.button("Open alert", id="open-alert")),
            rx.alert_dialog.content(
                rx.alert_dialog.title("Alert"),
                rx.alert_dialog.description("alert description"),
                rx.flex(
                    rx.alert_dialog.cancel(rx.button("Cancel", id="alert-cancel")),
                    rx.alert_dialog.action(rx.button("OK", id="alert-ok")),
                    spacing="3",
                ),
                id="alert-content",
            ),
        ),
        rx.drawer.root(
            rx.drawer.trigger(rx.button("Open drawer", id="open-drawer")),
            rx.drawer.overlay(z_index="5"),
            rx.drawer.portal(
                rx.drawer.content(
                    rx.drawer.title("Drawer"),
                    rx.drawer.close(rx.button("Close drawer", id="close-drawer")),
                    id="drawer-content",
                    background="white",
                    height="40%",
                    width="100%",
                    position="fixed",
                    bottom="0",
                    padding="1em",
                )
            ),
            direction="bottom",
        ),
        rx.popover.root(
            rx.popover.trigger(rx.button("Open popover", id="open-popover")),
            rx.popover.content(rx.text("Popover body", id="popover-body")),
        ),
        rx.text("opens=", DialogState.opens, id="dialog-opens"),
        rx.text("open=", DialogState.open.to_string(), id="dialog-open"),
    )


class SliderState(rx.State):
    single: list[int] = [50]
    committed: list[int] = [50]
    range_: list[int] = [20, 80]

    @rx.event
    def set_single(self, value: list[int]):
        self.single = value

    @rx.event
    def commit_single(self, value: list[int]):
        self.committed = value

    @rx.event
    def set_range(self, value: list[int]):
        self.range_ = value


def slider_page() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.slider(
            value=SliderState.single,
            on_change=SliderState.set_single,
            on_value_commit=SliderState.commit_single,
            min=0,
            max=100,
            step=1,
            width="300px",
            id="slider-single",
        ),
        rx.slider(
            default_value=[20, 80],
            on_change=SliderState.set_range,
            min=0,
            max=100,
            width="300px",
            id="slider-range",
        ),
        rx.text("single=", SliderState.single.join(","), id="single-value"),
        rx.text("committed=", SliderState.committed.join(","), id="committed-value"),
        rx.text("range=", SliderState.range_.join(","), id="range-value"),
    )


class FormState(rx.State):
    data: str = ""
    submits: int = 0

    @rx.event
    def submit(self, form_data: dict):
        self.submits += 1
        self.data = json.dumps(form_data)


def rform_page() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.form.root(
            rx.form.field(
                rx.form.label("Email"),
                rx.form.control(
                    rx.input(type="email", required=True, placeholder="email", id="f-email"),
                    as_child=True,
                ),
                rx.form.message("Email is required", match="valueMissing"),
                rx.form.message("Not an email", match="typeMismatch"),
                name="email",
            ),
            rx.form.field(
                rx.form.label("Age"),
                rx.form.control(
                    rx.input(type="number", min=18, placeholder="age", id="f-age"),
                    as_child=True,
                ),
                rx.form.message("Must be 18+", match="rangeUnderflow"),
                name="age",
            ),
            rx.form.submit(rx.button("Submit", id="f-submit"), as_child=True),
            on_submit=FormState.submit,
            reset_on_submit=True,
            id="rform",
            width="300px",
        ),
        rx.text("data=", FormState.data, id="f-data"),
        rx.text("submits=", FormState.submits, id="f-submits"),
    )


class MomentState(rx.State):
    prov_locale: str = "de"
    changes: int = 0
    last: str = ""

    @rx.event
    def set_prov_locale(self, value: str):
        self.prov_locale = value

    @rx.event
    def on_change(self, value: str):
        self.changes += 1
        self.last = value


def moment_page() -> rx.Component:
    # CMP-11: un-localed siblings must stay English next to locale="fr".
    cmp11 = rx.vstack(
        rx.moment(D, format="dddd D MMMM YYYY", id="plain"),
        rx.moment("2020-01-01T00:00:00", from_now=True, id="fromnow"),
        rx.moment(D, format="dddd D MMMM YYYY", locale="fr", id="french"),
        rx.moment(D, format="dddd D MMMM YYYY", locale="en", id="english"),
        rx.moment(D, format="dddd D MMMM YYYY", id="plain2"),
        rx.moment(D, format="dddd D MMMM YYYY", with_title=True, id="titled"),
        id="cmp11",
    )
    if not NEW:
        return rx.vstack(nav(), cmp11, rx.text("provider n/a on prev", id="prov-na"))
    provider = rx.moment_provider(
        rx.moment(D, id="prov-default"),
        rx.moment(D, locale="en", id="prov-en"),
        rx.moment(D, format="YYYY", id="prov-fmt"),
        rx.moment("2020-01-01T00:00:00", from_now=True, id="prov-fromnow"),
        rx.moment("2024-03-14T23:30:00Z", format="YYYY-MM-DD HH:mm", id="prov-tz"),
        locale="fr",
        format="D MMM YYYY",
        timezone="Europe/Paris",
        id="provider",
    )
    outside = rx.moment(D, format="D MMM YYYY", id="outside")
    provider_var = rx.moment_provider(
        rx.moment(D, format="dddd", id="prov-var"),
        rx.moment(D, format="dddd", locale="fr", id="prov-var-fr"),
        rx.moment("2020-01-01T00:00:00", from_now=True, id="prov-var-fromnow"),
        locale=MomentState.prov_locale,
        id="provider-var",
    )
    pooled = rx.moment_provider(
        rx.moment(interval=1000, format="HH:mm:ss", id="clock1"),
        rx.moment(interval=1000, format="HH:mm:ss", id="clock2"),
        pool=True,
        interval=1000,
        id="provider-pool",
    )
    opts = rx.vstack(
        rx.moment("2024-03-14T23:30:00Z", utc=True, format="YYYY-MM-DD HH:mm", id="utc"),
        rx.moment("2024-03-14T23:30:00Z", format="YYYY-MM-DD HH:mm", id="noutc"),
        rx.moment(D, calendar=True, id="calendar"),
        rx.moment(D, from_="2024-03-10T15:09:26", id="from"),
        rx.moment(D, from_="2024-03-10T15:09:26", ago=True, id="from-ago"),
        rx.moment(D, to="2024-03-20T15:09:26", id="to"),
        rx.moment("2020-01-01T00:00:00", from_now=True, ago=True, id="ago"),
        rx.moment(D, element="span", format="YYYY", id="element"),
        rx.moment("garbage", fallback="INVALID", id="fallback"),
        rx.moment(
            D,
            format="MMMM",
            filters=[rx.Var("(content) => content.toUpperCase()")],
            id="filters",
        ),
        rx.moment(
            D,
            renderers=[rx.Var("({ datetime }) => 'R:' + datetime.format('YYYY')")],
            id="renderers",
        ),
        rx.moment(D, format="YYYY", on_change=MomentState.on_change, id="onchange"),
        id="opts",
    )
    return rx.vstack(
        nav(),
        cmp11,
        provider,
        outside,
        provider_var,
        pooled,
        opts,
        rx.hstack(
            rx.button("de", on_click=MomentState.set_prov_locale("de"), id="loc-de"),
            rx.button("es", on_click=MomentState.set_prov_locale("es"), id="loc-es"),
            rx.button("en", on_click=MomentState.set_prov_locale("en"), id="loc-en"),
        ),
        rx.text("prov_locale=", MomentState.prov_locale, id="prov-locale"),
        rx.text("changes=", MomentState.changes, id="moment-changes"),
        rx.text("last=", MomentState.last, id="moment-last"),
    )


class DEState(rx.State):
    cols: list[dict[str, Any]] = [
        {"title": "Name"},
        {"title": "Age", "type": "int"},
        {"title": "Birth", "id": "date", "width": 120},
    ]
    rows_: list[list[Any]] = [
        ["Ann", 30, "1990-01-01"],
        ["Bob", 41, "1980-02-02"],
        ["Cid", 52, "1970-03-03"],
    ]
    title_cols: list[str] = ["Code", "Value"]
    title_rows: list[list[Any]] = [["A", "1"], ["B", "2"]]
    edits: str = ""
    appended: int = 0

    @rx.event
    def cell_edited(self, pos: tuple[int, int], value: dict):
        col, row = pos
        self.rows_[row][col] = value.get("data")
        self.edits = f"{col},{row}={value.get('data')}"

    @rx.event
    def add_row(self):
        self.rows_.append([f"New{len(self.rows_)}", 0, "2000-01-01"])
        self.appended += 1

    @rx.event
    def add_col(self):
        self.cols.append({"title": f"Extra{len(self.cols)}"})
        for r in self.rows_:
            r.append("x")


def de_page() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.box(
            rx.data_editor(
                columns=DEState.cols,
                data=DEState.rows_,
                on_cell_edited=DEState.cell_edited,
                on_row_appended=DEState.add_row,
                id="de1",
            ),
            id="de1-box",
            width="500px",
        ),
        rx.box(
            rx.data_editor(
                # 0.10.0 rejects a list[str] state var for columns (#7607 added it).
                columns=DEState.title_cols if NEW else [{"title": "Code"}, {"title": "Value"}],
                data=DEState.title_rows,
                id="de2",
            ),
            id="de2-box",
            width="400px",
        ),
        rx.box(
            rx.data_editor(
                columns=[
                    {"title": "Preview", "type": "image", "width": 120},
                    {"title": "Name"},
                    "Plain",
                ],
                data=[[["/img1.png", "/img2.png"], "Red+Blue", "p1"], [["/img2.png"], "Blue", "p2"]],
                row_height=60,
                id="de3",
            ),
            id="de3-box",
            width="400px",
        ),
        rx.box(
            rx.data_editor(columns=DEState.cols, data=DEState.rows_[1:], id="de4"),
            id="de4-box",
            width="500px",
        ),
        rx.hstack(
            rx.button("add row", on_click=DEState.add_row, id="de-add-row"),
            rx.button("add col", on_click=DEState.add_col, id="de-add-col"),
        ),
        rx.text("edits=", DEState.edits, id="de-edits"),
        rx.text("appended=", DEState.appended, id="de-appended"),
        rx.text("ncols=", DEState.cols.length(), id="de-ncols"),
        rx.text("nrows=", DEState.rows_.length(), id="de-nrows"),
        rx.text("row0=", DEState.rows_[0].join("|"), id="de-row0"),
    )


class IconState(rx.State):
    name: str = "apple"
    size: int = 24
    names: list[str] = ["banana", "cherry", "grape"]

    @rx.event
    def next_icon(self):
        order = ["apple", "banana", "wifi_off", "circle_help"]
        self.name = order[(order.index(self.name) + 1) % len(order)]

    @rx.event
    def bigger(self):
        self.size += 8


icon_count_size = rx.Var(
    "Math.min(Object.keys(lucideIcons).length, 40)",
    _var_type=int,
    _var_data=rx.vars.VarData(
        imports={LUCIDE_LIBRARY: [ImportVar("icons", alias="lucideIcons")]}
    ),
)


def icons_page() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.icon("apple", id="static-icon"),
        rx.icon("banana", id="ref-banana"),
        rx.icon("wifi_off", id="ref-wifi-off"),
        rx.button(rx.icon("search"), "Search", id="btn-icon"),
        rx.input(rx.input.slot(rx.icon("mail")), placeholder="mail", id="slot-input"),
        rx.badge(rx.icon("check", size=12), "ok", id="badge-icon"),
        rx.callout("callout", icon="info", id="callout-icon"),
        rx.icon(IconState.name, id="dyn-icon"),
        rx.hstack(rx.foreach(IconState.names, lambda n: rx.icon(n, size=16)), id="foreach-icons"),
        rx.icon("sun", color=rx.color_mode_cond("red", "blue"), id="cm-icon"),
        rx.icon("moon", on_click=rx.toggle_color_mode, id="toggle-icon"),
        rx.icon("star", size=IconState.size, id="size-icon"),
        rx.icon(IconState.name, color=rx.color_mode_cond("red", "blue"), id="dyn-cm-icon"),
        rx.icon("apple", size=icon_count_size, id="libprop-icon"),
        rx.icon(IconState.name, size=icon_count_size, id="dyn-libprop-icon"),
        rx.button("next", on_click=IconState.next_icon, id="icon-next"),
        rx.button("bigger", on_click=IconState.bigger, id="icon-bigger"),
        rx.text("name=", IconState.name, id="icon-name"),
        rx.text("size=", IconState.size, id="icon-size"),
    )


PY_CODE = """def hello(name):  # [!code highlight]
    print("hi", name)
    return name  # [!code ++]
    return None  # [!code --]
"""

JS_CODE = """function add(a, b) {
  return a + b;
}
"""


def code_page() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.box(
            rx._x.code_block(PY_CODE, language="python", use_transformers=True),
            id="shiki-t",
        ),
        rx.box(rx._x.code_block(PY_CODE, language="python"), id="shiki-plain"),
        rx.box(
            rx._x.code_block(PY_CODE, language="python", use_transformers=True, show_line_numbers=True, can_copy=True),
            id="shiki-t-ln",
        ),
        rx.box(
            rx.code_block(PY_CODE, language="python", show_line_numbers=True, can_copy=True),
            id="rsh-py",
        ),
        rx.box(rx.code_block(JS_CODE, language="javascript", theme=rx.code_block.themes.dark), id="rsh-js"),
        rx.box(rx.code_block(JS_CODE, language="javascript", theme=rx.code_block.themes.one_light), id="rsh-light"),
        rx.box(rx.markdown("```python\nprint('md')\n```\n\n```js\nconsole.log('md')\n```"), id="md-code"),
    )


app = rx.App()
app.add_page(index, route="/")
app.add_page(cbg_page, route="/cbg")
app.add_page(radio_page, route="/radio")
app.add_page(radio_aschild_page, route="/radio_aschild")
app.add_page(input_page, route="/input")
app.add_page(progress_page, route="/progress")
app.add_page(accordion_page, route="/accordion")
app.add_page(dialog_page, route="/dialog")
app.add_page(slider_page, route="/slider")
app.add_page(rform_page, route="/rform")
app.add_page(moment_page, route="/moment")
app.add_page(de_page, route="/de")
app.add_page(icons_page, route="/icons")
app.add_page(code_page, route="/code")
