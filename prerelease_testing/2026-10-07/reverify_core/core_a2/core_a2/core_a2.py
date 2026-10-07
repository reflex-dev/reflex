"""E2E app for reflex 0.10.0a2: #7456 (backend var formatting), #7461 (class-assigned defaults), #7465 (dunders).

Loads on 0.9.12 / 0.10.0a1 too (version-agnostic helpers), so the same source gives baselines.
"""

import os
from typing import ClassVar

import reflex as rx


def const(cls, name):
    """Read a declared backend default in a way that works on every version (0.9.12 get_fields()[n].default_value())."""
    return cls.get_fields()[name].default_value()


# ---------- "/" : F-001 / F-004 ----------
class ConstState(rx.State):
    _LABEL = "label-const"
    _SIZE: int = 16
    _ITEMS: list[str] = ["i1", "i2"]
    LABEL_CV: ClassVar[str] = "classvar-const"


class Cfg(rx.State):
    _key: str | None = None
    shown: str = ""
    log: list[str] = []

    @rx.event
    def show(self):
        self.shown = f"key={self._key!r}"
        self.log.append(self.shown)

    @rx.event
    def set_instance(self):
        self._key = "set-on-instance"

    @rx.event
    def do_reset(self):
        self.reset()
        self.log.append("reset-done")


Cfg._key = "sk_live"


class Counter(rx.ComponentState):
    count: int = 0
    _step = 5

    @rx.event
    def incr(self):
        self.count += self._step

    @classmethod
    def get_component(cls, **props):
        return rx.hstack(
            rx.button(f"+{const(cls, '_step')}", on_click=cls.incr, id="cs_btn"),
            rx.text(cls.count, id="cs_count"),
        )


def index():
    return rx.vstack(
        rx.heading("classattr"),
        rx.text(f"label={const(ConstState, '_LABEL')}", id="fstring_label"),
        rx.box(rx.text("sized"), width=f"{const(ConstState, '_SIZE')}px", id="sized"),
        rx.foreach(const(ConstState, "_ITEMS"), lambda i: rx.text(i, class_name="item")),
        rx.text(ConstState.LABEL_CV, id="classvar_label"),
        Counter.create(),
        rx.button("show", id="show", on_click=Cfg.show),
        rx.button("set_instance", id="set_instance", on_click=Cfg.set_instance),
        rx.button("reset", id="reset", on_click=Cfg.do_reset),
        rx.text(Cfg.shown, id="shown"),
        rx.text(Cfg.log.join(" | "), id="log"),
        rx.link("cs", href="/cs", id="nav_cs"),
    )


# ---------- "/cs" : #7461 ComponentState per-instance defaults ----------
class Ctr(rx.ComponentState):
    count: int = 0
    label: str = "none"
    tags: list[str] = []
    _hidden: int = 0
    hidden_view: str = ""

    @rx.event
    def incr(self):
        self.count += 1
        self.tags.append(f"t{self.count}")

    @rx.event
    def do_reset(self):
        self.reset()

    @rx.event
    def show_hidden(self):
        self._hidden += 1
        self.hidden_view = f"hidden={self._hidden}"

    @rx.event
    def reconfigure(self):
        type(self).count = 77
        self.reset()

    @classmethod
    def get_component(cls, start: int = 0, tag: str = "x", **props):
        cls.count = 1  # overwritten below: reset must restore the LAST configured default
        cls.count = start
        cls.label = f"lbl{start}"
        cls.tags = [f"init{start}"]
        cls._hidden = start * 100
        return rx.hstack(
            rx.text(cls.count, id=f"count_{tag}"),
            rx.text(cls.label, id=f"label_{tag}"),
            rx.text(cls.tags.join(","), id=f"tags_{tag}"),
            rx.text(cls.hidden_view, id=f"hidden_{tag}"),
            rx.button("+", on_click=cls.incr, id=f"incr_{tag}"),
            rx.button("reset", on_click=cls.do_reset, id=f"reset_{tag}"),
            rx.button("hidden", on_click=cls.show_hidden, id=f"showhidden_{tag}"),
            rx.button("reconf", on_click=cls.reconfigure, id=f"reconf_{tag}"),
        )


class EditableText(rx.ComponentState):
    """Verbatim from the a2 docs (docs/state_structure/component_state.md, EditableText)."""

    text: str = "Click to edit"
    original_text: str
    editing: bool = False

    @rx.event
    def set_text(self, value: str):
        self.text = value

    @rx.event
    def start_editing(self, original_text: str):
        self.original_text = original_text
        self.editing = True

    @rx.event
    def stop_editing(self):
        self.editing = False
        self.original_text = ""

    @classmethod
    def get_component(cls, **props):
        value = props.pop("value", cls.text)
        on_change = props.pop("on_change", cls.set_text)
        cursor = props.pop("cursor", "pointer")
        initial_value = props.pop("initial_value", None)
        if initial_value is not None:
            cls.text = initial_value
        edit_controls = rx.hstack(
            rx.input(value=value, on_change=on_change, **props),
            rx.icon_button(rx.icon("x"), on_click=[on_change(cls.original_text), cls.stop_editing], type="button", color_scheme="red"),
            rx.icon_button(rx.icon("check")),
            align="center",
            width="100%",
        )
        return rx.cond(
            cls.editing,
            rx.form(edit_controls, on_submit=lambda _: cls.stop_editing()),
            rx.text(value, on_click=cls.start_editing(value), cursor=cursor, **props),
        )


def cs_page():
    return rx.vstack(
        rx.heading("component state"),
        Ctr.create(start=10, tag="a"),
        Ctr.create(start=20, tag="b"),
        rx.box(EditableText.create(), id="et_default"),
        rx.box(EditableText.create(initial_value="Edit me!", color="blue"), id="et_editme"),
        rx.box(EditableText.create(initial_value="Reflex is fun", font_family="monospace"), id="et_fun"),
        rx.link("home", href="/", id="nav_home"),
    )


# ---------- "/storage" : #7461 browser storage + factories ----------
class St(rx.State):
    ls_fac_assigned: str = rx.LocalStorage("x", name="ls_fac_key")
    ls_declared_fac: rx.LocalStorage = rx.field(
        default_factory=lambda: rx.LocalStorage("decl-fac", name="decl_fac_key", sync=True)
    )
    ls_plain: str = rx.LocalStorage("ls-default", name="ls_plain_key")
    ls_untouched: str = rx.LocalStorage("untouched-default", name="ls_untouched_key")
    ck: str = rx.Cookie("ck-default", name="ck_key", max_age=3600)

    @rx.event
    def change_all(self):
        self.ls_fac_assigned = "changed-fac"
        self.ls_declared_fac = "changed-decl"
        self.ls_plain = "changed-plain"
        self.ls_untouched = "changed-untouched"
        self.ck = "changed-ck"

    @rx.event
    def do_reset(self):
        self.reset()


if os.environ.get("CORE_ASSIGN_STORAGE", "1") == "1":
    St.ls_fac_assigned = lambda: rx.LocalStorage("from-factory", name="ls_fac_key2", sync=True)
    St.ls_plain = "assigned-plain"
    St.ck = "assigned-ck"


class LsCS(rx.ComponentState):
    """Storage-backed ComponentState configured the documented way (cls.value = initial)."""

    value: str = rx.LocalStorage("cs-default", name="lscs_key")

    @rx.event
    def change(self):
        self.value = "cs-changed"

    @classmethod
    def get_component(cls, **props):
        initial = props.pop("initial", None)
        if initial is not None:
            cls.value = initial
        return rx.hstack(rx.text(cls.value, id="lscs_value"), rx.button("change", on_click=cls.change, id="lscs_change"))


def storage_page():
    return rx.vstack(
        rx.heading("storage"),
        rx.text(St.ls_fac_assigned, id="v_ls_fac_assigned"),
        rx.text(St.ls_declared_fac, id="v_ls_declared_fac"),
        rx.text(St.ls_plain, id="v_ls_plain"),
        rx.text(St.ls_untouched, id="v_ls_untouched"),
        rx.text(St.ck, id="v_ck"),
        rx.button("change all", on_click=St.change_all, id="change_all"),
        rx.button("reset", on_click=St.do_reset, id="st_reset"),
        LsCS.create(initial="cs-initial"),
    )


# ---------- "/dunder" : #7465 ----------
class Params:
    @classmethod
    def from_request(cls, x):
        return f"Params({x})"


class DMx(rx.State, mixin=True):
    __mx = 0

    @rx.event
    def bump_mx(self):
        self.__mx += 1
        self.view = f"mx={self.__mx}"


class D(DMx, rx.State):
    __counter = 0
    __data_source_params_class__ = Params
    __fielded: rx.Field[int] = rx.field(0) if hasattr(rx, "Field") else 0
    view: str = ""

    @rx.event
    def bump(self):
        self.__counter += 1
        self.view = f"counter={self.__counter}"

    @rx.event
    def bump_silent(self):
        self.__counter += 1

    @rx.event
    def bump_fielded(self):
        self.__fielded += 1

    @rx.event
    def show(self):
        self.view = f"counter={self.__counter} fielded={self.__fielded} params={type(self).__data_source_params_class__.from_request(1)}"

    @rx.var
    def counter_cv(self) -> int:
        return self.__counter

    @rx.var
    def fielded_cv(self) -> int:
        return self.__fielded


def dunder_page():
    return rx.vstack(
        rx.heading("dunder"),
        rx.text(D.view, id="d_view"),
        rx.text(D.counter_cv, id="d_counter_cv"),
        rx.text(D.fielded_cv, id="d_fielded_cv"),
        rx.button("bump", on_click=D.bump, id="d_bump"),
        rx.button("bump_silent", on_click=D.bump_silent, id="d_bump_silent"),
        rx.button("bump_fielded", on_click=D.bump_fielded, id="d_bump_fielded"),
        rx.button("bump_mx", on_click=D.bump_mx, id="d_bump_mx"),
        rx.button("show", on_click=D.show, id="d_show"),
    )


# ---------- "/schema" : default changed between restarts ----------
class Sch(rx.State):
    count: int = int(os.environ.get("CORE_DEFAULT", "0"))
    note: str = "fresh"

    @rx.event
    def set42(self):
        self.count = 42
        self.note = "saved-before-restart"


def schema_page():
    return rx.vstack(
        rx.text(Sch.count, id="sch_count"),
        rx.text(Sch.note, id="sch_note"),
        rx.button("set42", on_click=Sch.set42, id="sch_set42"),
    )


app = rx.App()
_PAGES = os.environ.get("CORE_PAGES", "home,cs,storage,dunder,schema").split(",")
app.add_page(index)
if "cs" in _PAGES:
    app.add_page(cs_page, route="/cs")
if "storage" in _PAGES:
    app.add_page(storage_page, route="/storage")
if "dunder" in _PAGES:
    app.add_page(dunder_page, route="/dunder")
if "schema" in _PAGES:
    app.add_page(schema_page, route="/schema")
