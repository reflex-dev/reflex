"""Form submission payload tests (#7227)."""

import json
from typing import Any

import reflex as rx

from .common import nav


class RatingControl(rx.el.Div):
    """A custom, non-native control that opts in as a form control."""

    _is_form_control = True


class NotAControl(rx.el.Div):
    """A custom div with an id that is NOT a form control."""


class NativeSelect(rx.el.Select):
    """A custom subclass of the native select element."""


def _dump(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, default=str)


class FormState(rx.State):
    """Collects payloads of each form."""

    main_payload: str = ""
    dialog_payload: str = ""
    main_count: int = 0
    dialog_count: int = 0
    deb: str = ""

    @rx.event
    def main_submit(self, form_data: dict[str, Any]):
        self.main_count += 1
        self.main_payload = _dump(form_data)
        print("FORM_MAIN", self.main_count, self.main_payload, flush=True)

    @rx.event
    def dialog_submit(self, form_data: dict[str, Any]):
        self.dialog_count += 1
        self.dialog_payload = _dump(form_data)
        print("FORM_DIALOG", self.dialog_count, self.dialog_payload, flush=True)

    @rx.event
    def set_deb(self, value: str):
        self.deb = value


class FormCS(rx.ComponentState):
    """A ComponentState-owned form (two instances)."""

    payload: str = ""
    count: int = 0

    @rx.event
    def submit(self, form_data: dict[str, Any]):
        self.count += 1
        self.payload = _dump(form_data)
        print("FORM_CS", self.count, self.payload, flush=True)

    @classmethod
    def get_component(cls, **props) -> rx.Component:
        p = props.pop("prefix")
        return rx.vstack(
            rx.form(
                rx.hstack(
                    rx.input(id=f"{p}_text"),
                    rx.switch(id=f"{p}_sw"),
                    rx.text("label", id=f"{p}_label"),
                    rx.button("Go", type="submit", id=f"{p}_go"),
                    id=f"{p}_wrap",
                ),
                on_submit=cls.submit,
                id=f"{p}_form",
            ),
            rx.text(cls.count, " ", cls.payload, id=f"{p}_payload"),
        )


cs_form_1 = FormCS.create(prefix="csf1")
cs_form_2 = FormCS.create(prefix="csf2")


def forms_page() -> rx.Component:
    """Form page with every control kind, a dialog with a nested form, and CS forms."""
    return rx.vstack(
        nav(),
        rx.heading("Form payloads"),
        rx.form(
            rx.vstack(
                rx.text("Main form label", id="f_label"),
                rx.input(id="f_text"),
                rx.input(name="f_named", default_value="abc"),
                rx.el.input(id="f_native"),
                rx.slider(id="f_slider", default_value=[30], width="200px"),
                rx.checkbox(id="f_check"),
                rx.checkbox(id="f_check_on", default_checked=True),
                rx.switch(id="f_switch"),
                rx.radio_group(["x", "y"], id="f_radio"),
                rx.select(["s1", "s2"], id="f_select"),
                rx.text_area(id="f_textarea"),
                rx.input(id="f_debounced", value=FormState.deb, on_change=FormState.set_deb),
                NativeSelect.create(
                    rx.el.option("n1", value="n1"),
                    rx.el.option("n2", value="n2"),
                    id="f_native_select",
                ),
                RatingControl.create(
                    rx.el.label(rx.el.input(type="radio", name="rating_native", value="1"), "1"),
                    rx.el.label(rx.el.input(type="radio", name="rating_native", value="3", id="rating3"), "3"),
                    id="f_rating",
                ),
                NotAControl.create(rx.text("not a control"), id="f_notcontrol"),
                rx.upload(rx.text("drop files"), id="f_upload", border="1px dashed gray", padding="4px"),
                rx.box(
                    rx.data_editor(
                        columns=[{"title": "A", "type": "str"}],
                        data=[["cell"]],
                        id="f_grid",
                        width="200px",
                        height="80px",
                    ),
                    width="200px",
                    height="80px",
                ),
                rx.dialog.root(
                    rx.dialog.trigger(rx.button("Open dialog", type="button", id="open_dialog")),
                    rx.dialog.content(
                        rx.dialog.title("Nested form"),
                        rx.form(
                            rx.input(id="d_text"),
                            rx.checkbox(id="d_check"),
                            rx.button("Dialog submit", type="submit", id="d_submit"),
                            on_submit=FormState.dialog_submit,
                            id="dialog_form",
                        ),
                        rx.dialog.close(rx.button("Close", type="button", id="d_close")),
                    ),
                ),
                rx.button("Submit", type="submit", id="f_submit"),
                id="f_wrapper",
            ),
            on_submit=FormState.main_submit,
            id="main_form",
        ),
        rx.text(FormState.main_count, id="main_count"),
        rx.text(FormState.main_payload, id="main_payload"),
        rx.text(FormState.dialog_count, id="dialog_count"),
        rx.text(FormState.dialog_payload, id="dialog_payload"),
        rx.heading("ComponentState forms", size="3"),
        cs_form_1,
        cs_form_2,
        padding="10px",
    )
