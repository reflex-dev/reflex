"""Forms behaviour probe: 0.10.0-style forms (dict handlers) that must compile on 0.10.0 and 0.10.1a1.

Every form's handler records exactly what it received (python type + JSON with key order kept) in
``State.results[<form>]`` which is rendered in ``pre#results``; ``span#seq`` counts submissions so a
driver can wait for the next one. The same record is appended to ``form_log.jsonl`` next to rxconfig.
"""

import dataclasses
import pydantic
import json
import os
import pathlib
from collections.abc import Mapping
from typing import Any

import reflex as rx

assert f"/envs/{os.environ.get('EXPECT_VENV', 'new')}/" in rx.__file__, rx.__file__

@dataclasses.dataclass
class DCForm:
    a: str = ""
    b: str = ""
    cb: bool = False


class PydForm(pydantic.BaseModel):
    a: str = ""
    b: str = ""
    cb: bool = False


LOG = pathlib.Path(__file__).resolve().parent.parent / "form_log.jsonl"


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return f"<{type(value).__name__}:{value!r}>"


class State(rx.State):
    results: dict[str, str] = {}
    seq: int = 0
    ctrl: str = "c1"
    ctrl2: str = "c2"
    ctrl3: str = "c3"
    ctrl4: str = "c4"
    ta_ctrl: str = "ta-ctrl"
    items: list[str] = ["alpha", "beta"]
    dyn_name: str = "dyn_field"
    dyn_val: str = "dyn-hidden"
    note: str = ""

    def _record(self, form: str, data: Any, extra: dict | None = None):
        rec = {
            "form": form,
            "type": type(data).__name__,
            "data": _jsonable(data),
        }
        if hasattr(data, "multi_items"):
            rec["multi_items"] = _jsonable(data.multi_items())
        if extra:
            rec.update(extra)
        self.results[form] = json.dumps(rec)
        self.seq += 1
        with LOG.open("a") as f:
            f.write(json.dumps(rec, default=str) + "\n")

    @rx.event
    def store(self, form: str, form_data: dict):
        self._record(form, form_data)

    @rx.event
    def store_any(self, form: str, form_data):
        self._record(form, form_data)

    @rx.event
    def store_dict_any(self, form: str, form_data: dict[str, Any]):
        self._record(form, form_data)

    @rx.event
    def store_dc(self, form: str, form_data: DCForm):
        self._record(form, dataclasses.asdict(form_data), {"pytype": type(form_data).__name__})

    @rx.event
    def store_pyd(self, form: str, form_data: PydForm):
        self._record(form, form_data.dict(), {"pytype": type(form_data).__name__})

    @rx.event
    def store_mapping(self, form: str, form_data: Mapping[str, Any]):
        self._record(form, dict(form_data))

    @rx.event
    def store_optdict(self, form: str, form_data: dict | None):
        self._record(form, form_data)

    @rx.event
    def store_anyarg(self, form: str, form_data: Any):
        self._record(form, form_data)

    @rx.event
    def chain_first(self, form_data: dict):
        self._record("chain_first", form_data)
        return State.chain_second(form_data)

    @rx.event
    def chain_second(self, form_data: dict):
        self._record("chain_second", form_data)

    @rx.event
    def after_submit(self):
        self.note = "after_submit ran"

    @rx.event
    def set_ctrl(self, v: str):
        self.ctrl = v

    @rx.event
    def set_ctrl2(self, v: str):
        self.ctrl2 = v

    @rx.event
    def set_ctrl3(self, v: str):
        self.ctrl3 = v

    @rx.event
    def set_ctrl4(self, v: str):
        self.ctrl4 = v

    @rx.event
    def set_ta_ctrl(self, v: str):
        self.ta_ctrl = v

    @rx.var
    def results_json(self) -> str:
        return json.dumps(self.results, sort_keys=True)


def wrap(key: str, *children, **form_props):
    """A form with a submit button inside a box identified by data-form=<key>."""
    return rx.box(
        rx.heading(key, size="3"),
        rx.form(
            rx.vstack(*children, rx.button("submit " + key, type="submit")),
            **form_props,
        ),
        custom_attrs={"data-form": key},
        border="1px solid gray",
        padding="4px",
        margin="4px",
    )


def legacy() -> rx.Component:
    return rx.vstack(
        rx.text("seq: ", rx.el.span(State.seq, id="seq"), " note: ", rx.el.span(State.note, id="note")),
        rx.el.pre(State.results_json, id="results", style={"white-space": "pre-wrap"}),
        # f01: every control with only an `id`
        wrap(
            "id_only",
            rx.input(id="io_email"),
            rx.text_area(id="io_ta"),
            rx.checkbox("cb", id="io_cb"),
            rx.switch(id="io_sw"),
            rx.select(["a", "b"], id="io_sel", default_value="a"),
            rx.radio_group(["r1", "r2"], id="io_rg"),
            rx.slider(default_value=[30], id="io_sl"),
            rx.el.input(type="hidden", id="io_hid", value="hv"),
            rx.el.input(type="checkbox", id="io_hcb"),
            rx.el.input(type="checkbox", id="io_hcb_checked", default_checked=True),
            on_submit=State.store("id_only"),
        ),
        # f02: same controls with only a `name`
        wrap(
            "name_only",
            rx.input(name="email"),
            rx.text_area(name="ta"),
            rx.checkbox("cb", name="cb"),
            rx.switch(name="sw"),
            rx.select(["a", "b"], name="sel", default_value="a"),
            rx.radio_group(["r1", "r2"], name="rg"),
            rx.slider(default_value=[30], name="sl"),
            rx.el.input(type="hidden", name="hid", value="hv"),
            rx.el.input(type="checkbox", name="hcb"),
            rx.el.input(type="checkbox", name="hcb_checked", default_checked=True),
            on_submit=State.store("name_only"),
        ),
        # f03: id == name
        wrap(
            "id_eq_name",
            rx.input(id="ien_email", name="ien_email"),
            rx.text_area(id="ien_ta", name="ien_ta"),
            rx.checkbox("cb", id="ien_cb", name="ien_cb"),
            rx.switch(id="ien_sw", name="ien_sw"),
            rx.select(["a", "b"], id="ien_sel", name="ien_sel", default_value="a"),
            rx.radio_group(["r1", "r2"], id="ien_rg", name="ien_rg"),
            rx.slider(default_value=[30], id="ien_sl", name="ien_sl"),
            rx.el.input(type="hidden", id="ien_hid", name="ien_hid", value="hv"),
            rx.el.input(type="checkbox", id="ien_hcb", name="ien_hcb"),
            rx.el.input(type="checkbox", id="ien_hcb_checked", name="ien_hcb_checked", default_checked=True),
            on_submit=State.store("id_eq_name"),
        ),
        # f04: id != name
        wrap(
            "id_ne_name",
            rx.input(id="idx", name="namex"),
            rx.checkbox("cb", id="cbid", name="cbname"),
            rx.switch(id="swid", name="swname"),
            rx.el.input(type="checkbox", id="hcbid", name="hcbname"),
            rx.slider(default_value=[30], id="slid", name="slname"),
            on_submit=State.store("id_ne_name"),
        ),
        # f05: groups / repeated names
        wrap(
            "groups",
            rx.checkbox_group.root(rx.checkbox_group.item("c1", value="c1"), rx.checkbox_group.item("c2", value="c2"), rx.checkbox_group.item("c3", value="c3"), name="cg"),
            rx.el.input(type="checkbox", name="topping", value="cheese"),
            rx.el.input(type="checkbox", name="topping", value="olives"),
            rx.el.input(type="checkbox", name="topping", value="ham"),
            rx.radio_group(["r1", "r2"], name="rg"),
            rx.el.input(type="radio", name="hr", value="x1"),
            rx.el.input(type="radio", name="hr", value="x2"),
            rx.input(name="rep", default_value="rep-first"),
            rx.input(name="rep", default_value="rep-second"),
            rx.el.select(
                rx.el.option("o1", value="o1"),
                rx.el.option("o2", value="o2"),
                rx.el.option("o3", value="o3"),
                name="hsel",
                multiple=True,
            ),
            on_submit=State.store("groups"),
        ),
        # f05b: checkbox group whose id equals its name (repeated name + id ref)
        wrap(
            "group_id_eq_name",
            rx.checkbox_group.root(rx.checkbox_group.item("c1", value="c1"), rx.checkbox_group.item("c2", value="c2"), rx.checkbox_group.item("c3", value="c3"), id="cg", name="cg"),
            rx.el.input(type="checkbox", id="topping", name="topping", value="cheese"),
            rx.el.input(type="checkbox", name="topping", value="olives"),
            on_submit=State.store("group_id_eq_name"),
        ),
        # f06: sliders
        wrap(
            "sliders",
            rx.slider(default_value=[30], name="sl"),
            rx.slider(default_value=[20, 80], name="range"),
            rx.slider(default_value=[20, 80], id="rangeid"),
            rx.slider(default_value=[20, 80], id="range2", name="range2"),
            on_submit=State.store("sliders"),
        ),
        # f07: controlled inputs
        wrap(
            "controlled",
            rx.input(value=State.ctrl, on_change=State.set_ctrl, name="ctrl"),
            rx.input(value=State.ctrl2, on_change=State.set_ctrl2, id="ctrl2"),
            rx.input(value=State.ctrl3, on_change=State.set_ctrl3, id="ctrl3", name="ctrl3"),
            rx.el.input(value=State.ctrl4, on_change=State.set_ctrl4, name="ctrl4"),
            rx.text_area(value=State.ta_ctrl, on_change=State.set_ta_ctrl, name="ta_ctrl"),
            rx.input(name="num", type="number", default_value="5"),
            rx.input(name="empty"),
            rx.input(name="disabled_named", default_value="dis", disabled=True),
            rx.input(id="disabled_id", default_value="dis", disabled=True),
            on_submit=State.store("controlled"),
        ),
        # f08: reset_on_submit
        wrap(
            "reset",
            rx.input(name="r1"),
            rx.checkbox("rcb", name="rcb"),
            on_submit=State.store("reset"),
            reset_on_submit=True,
        ),
        # f09: forms in foreach
        rx.box(
            rx.heading("foreach", size="3"),
            rx.foreach(
                State.items,
                lambda it: rx.form(
                    rx.input(name="item", default_value=it),
                    rx.el.input(type="hidden", name="which", value=it),
                    rx.el.input(type="hidden", id="which_id", value=it),
                    rx.button("submit foreach", type="submit"),
                    on_submit=State.store("foreach"),
                ),
            ),
            custom_attrs={"data-form": "foreach"},
        ),
        # f10: rx.el.form
        rx.box(
            rx.heading("el_form", size="3"),
            rx.el.form(
                rx.el.input(name="a", default_value="A"),
                rx.el.input(id="b", default_value="B"),
                rx.el.input(id="c", name="c", default_value="C"),
                rx.el.button("submit el_form", type="submit"),
                on_submit=State.store("el_form"),
            ),
            custom_attrs={"data-form": "el_form"},
        ),
        # f11: radix form.root with fields (name on the field, not the control)
        rx.box(
            rx.heading("radix_root", size="3"),
            rx.form.root(
                rx.form.field(
                    rx.form.control(rx.input(type="email", id="femail"), as_child=True),
                    name="email",
                ),
                rx.form.field(
                    rx.form.control(rx.input(default_value="agreed"), as_child=True),
                    name="agree",
                ),
                rx.form.field(
                    rx.form.control(rx.input(name="explicit"), as_child=True),
                    name="fieldname",
                ),
                rx.form.submit(rx.button("submit radix_root"), as_child=True),
                on_submit=State.store("radix_root"),
            ),
            custom_attrs={"data-form": "radix_root"},
        ),
        # f12: dynamic name from a var
        wrap(
            "dynamic",
            rx.input(name=State.dyn_name, default_value="dyn-value"),
            rx.el.input(type="hidden", name="h", value=State.dyn_val),
            rx.checkbox("dyncb", name=State.dyn_name + "_cb"),
            on_submit=State.store("dynamic"),
        ),
        # f13: unannotated handler, dict[str, Any] handler
        wrap(
            "unannotated",
            rx.input(name="u", default_value="U"),
            rx.input(id="uid", default_value="UID"),
            rx.checkbox("ucb", name="ucb"),
            on_submit=State.store_any("unannotated"),
        ),
        wrap(
            "dict_any",
            rx.input(name="u", default_value="U"),
            rx.input(id="uid", default_value="UID"),
            on_submit=State.store_dict_any("dict_any"),
        ),
        # f14: lambda passing the data on
        wrap(
            "lambda",
            rx.input(name="l", default_value="L"),
            rx.input(id="lid", default_value="LID"),
            on_submit=lambda fd: State.store("lambda", fd),
        ),
        # f15: chain: handler passes the form data to a second handler; a no-arg handler follows
        wrap(
            "chain",
            rx.input(name="ch", default_value="CH"),
            rx.el.input(type="checkbox", name="topping", value="a", default_checked=True),
            rx.el.input(type="checkbox", name="topping", value="b", default_checked=True),
            on_submit=[State.chain_first, State.after_submit],
        ),
        # f16: file input (binary attachment path in socket.io)
        wrap(
            "file",
            rx.input(name="ftext", default_value="with-file"),
            rx.el.input(type="file", name="f"),
            rx.el.input(type="checkbox", name="topping", value="a", default_checked=True),
            rx.el.input(type="checkbox", name="topping", value="b", default_checked=True),
            on_submit=State.store("file"),
        ),
        # f17: low-level radix select + native select, radio cards
        wrap(
            "selects",
            rx.select.root(
                rx.select.trigger(),
                rx.select.content(rx.select.item("i1", value="i1"), rx.select.item("i2", value="i2")),
                name="sel2",
                default_value="i1",
            ),
            rx.el.select(
                rx.el.option("o1", value="o1"),
                rx.el.option("o2", value="o2"),
                name="hsel_single",
                default_value="o2",
            ),
            rx.el.select(
                rx.el.option("o1", value="o1"),
                rx.el.option("o2", value="o2"),
                id="hsel_id",
                default_value="o2",
            ),
            rx.radio_cards.root(
                rx.radio_cards.item("rc1", value="rc1"),
                rx.radio_cards.item("rc2", value="rc2"),
                name="rc",
                default_value="rc2",
            ),
            on_submit=State.store("selects"),
        ),
        # f19: non-dict annotations for the form data: Mapping, dict | None, Any (dataclass / pydantic models are rejected at compile time on 0.10.0 and 0.10.1a1 alike)
        wrap("mapping", rx.input(name="a", default_value="A"), rx.input(name="a", default_value="A2"), on_submit=State.store_mapping("mapping")),
        wrap("optdict", rx.input(name="a", default_value="A"), rx.input(name="a", default_value="A2"), on_submit=State.store_optdict("optdict")),
        wrap("anyarg", rx.input(name="a", default_value="A"), rx.input(name="a", default_value="A2"), on_submit=State.store_anyarg("anyarg")),
        # f18: names ending in [] on plain inputs, and a bracketed id
        wrap(
            "brackets",
            rx.input(name="tags[]", default_value="t1"),
            rx.input(name="tags[]", default_value="t2"),
            rx.input(name="single[]", default_value="s1"),
            on_submit=State.store("brackets"),
        ),
    )


app = rx.App()
app.add_page(legacy, route="/legacy", title="legacy forms")
app.add_page(lambda: rx.text("index"), route="/", title="index")

if os.environ.get("FORMS_NEW") == "1":
    from . import newforms  # noqa: E402

    app.add_page(newforms.new_page, route="/new", title="new forms")
    app.add_page(newforms.future_page, route="/future", title="future forms")


class UpState(State):
    """CMP-01: record what the upload handler sees for hostile filenames; write with file.name (docs pattern)."""

    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        updir = rx.get_upload_dir().resolve()
        for f in files:
            rec = {"form": "upload", "filename": f.filename, "name": f.name, "path": str(f.path)}
            try:
                target = (updir / f.name).resolve()
                rec["target"] = str(target)
                rec["inside"] = str(target).startswith(str(updir) + "/")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(await f.read())
                rec["written"] = True
            except Exception as e:  # noqa: BLE001
                rec["error"] = f"{type(e).__name__}: {e}"
            try:
                ptarget = (updir / f.path).resolve()
                rec["path_target"] = str(ptarget)
                rec["path_inside"] = str(ptarget).startswith(str(updir) + "/")
            except Exception as e:  # noqa: BLE001
                rec["path_error"] = f"{type(e).__name__}: {e}"
            with LOG.open("a") as fh:
                fh.write(json.dumps(rec, default=str) + "\n")
            self.seq += 1


def upload_page() -> rx.Component:
    return rx.vstack(
        rx.upload(rx.text("drop"), id="up1"),
        rx.button("go", on_click=UpState.handle_upload(rx.upload_files(upload_id="up1"))),
        rx.el.span(State.seq, id="seq"),
    )


app.add_page(upload_page, route="/upload", title="upload")
