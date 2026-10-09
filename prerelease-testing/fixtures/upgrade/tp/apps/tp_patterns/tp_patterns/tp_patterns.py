"""Downstream-style State patterns, identical source for reflex 0.9.12 and 0.10.0a1."""

from __future__ import annotations

import json
import traceback

import reflex as rx
from reflex_base.event import BACKGROUND_TASK_MARKER

from .pkg import (
    PkgBaseState,
    PkgCounterMixin,
    PkgOtherState,
    backend_var_names,
    own_backend_var_names,
)

try:
    from importlib.metadata import version as _v

    REFLEX_VERSION = _v("reflex")
except Exception:  # noqa: BLE001
    REFLEX_VERSION = "?"
IS_010 = REFLEX_VERSION.startswith("0.10")


def links() -> rx.Component:
    return rx.hstack(
        *[rx.link(r, href=f"/{r}") for r in ["storage", "mixins", "inherit", "classattr", "background"]],
        spacing="3",
    )


@rx.page(route="/")
def index() -> rx.Component:
    return rx.vstack(rx.heading(f"tp_patterns on reflex {REFLEX_VERSION}"), links())


class StoreState(rx.State):
    ls_cv: str = rx.LocalStorage(name="tp_ls_cv")
    ls_onload: str = rx.LocalStorage(name="tp_ls_onload")
    ls_event: str = rx.LocalStorage(name="tp_ls_event")
    ls_nd: str = rx.LocalStorage(name="tp_ls_nd")
    ck_onload: str = rx.Cookie(name="tp_ck_onload")
    log: list[str] = []

    @rx.var(cache=True)
    def cv_check(self) -> str:
        # Same shape as reflex-google-auth's GoogleAuthState.tokeninfo: a computed var
        # that clears an invalid client-storage value it was computed from.
        if self.ls_cv == "bad":
            self.ls_cv = ""
            return "cleared-in-computed-var"
        return f"value={self.ls_cv!r}"

    @rx.event
    def on_load(self):
        if self.ls_onload == "bad":
            self.ls_onload = ""
        if self.ck_onload == "bad":
            self.ck_onload = ""
        if self.ls_nd == "bad":
            self.ls_nd = "fixed"
        self.log.append(f"on_load(ls_onload={self.ls_onload!r})")

    @rx.event
    def reset_event(self):
        if self.ls_event == "bad":
            self.ls_event = ""
        self.log.append("reset_event ran")


@rx.page(route="/storage", on_load=StoreState.on_load)
def storage() -> rx.Component:
    return rx.vstack(
        links(),
        rx.text("ls_cv=", StoreState.ls_cv, id="ls_cv"),
        rx.text("cv_check=", StoreState.cv_check, id="cv_check"),
        rx.text("ls_onload=", StoreState.ls_onload, id="ls_onload"),
        rx.text("ck_onload=", StoreState.ck_onload, id="ck_onload"),
        rx.text("ls_nd=", StoreState.ls_nd, id="ls_nd"),
        rx.text("ls_event=", StoreState.ls_event, id="ls_event"),
        rx.text(StoreState.log.join(" | "), id="store_log"),
        rx.button("reset event", id="reset_event", on_click=StoreState.reset_event),
    )


class MixA(PkgCounterMixin, rx.State):
    label: str = "A"


class MixB(PkgCounterMixin, rx.State):
    label: str = "B"

    @rx.var
    def doubled(self) -> int:  # override the mixin's computed var
        return self.count * 20


@rx.page(route="/mixins")
def mixins() -> rx.Component:
    return rx.vstack(
        links(),
        rx.button("A+", id="a_inc", on_click=MixA.incr),
        rx.button("B+", id="b_inc", on_click=MixB.incr),
        rx.button("A slow+10 (background)", id="a_slow", on_click=MixA.slow_incr),
        rx.text(MixA.label, " count=", MixA.count, " doubled=", MixA.doubled, " ", MixA.hits_view, id="a_view"),
        rx.text(MixB.label, " count=", MixB.count, " doubled=", MixB.doubled, " ", MixB.hits_view, id="b_view"),
    )


class UserState(PkgBaseState):
    extra: str = ""

    def _decorate(self) -> str:  # override the package hook
        return "user"

    @rx.event
    def add_twice(self):
        self.add("x")
        self.add("y")
        self.extra = f"secret={self._secret} n={self.n_items}"

    @rx.event
    async def touch_other(self):
        other = await self.get_state(PkgOtherState)
        other.remote = f"touched by {type(self).__name__}"
        other._remote_hits += 1
        self.note = f"other hits={other._remote_hits}"

    @rx.event
    def read_values(self):
        self.extra = f"get_value(items)={self.get_value('items')!r} get_value(_secret)={self.get_value('_secret')!r}"


PkgOtherState.add_var("dyn_added", int, 7)


def _dyn_bump(self):
    self.value += 1


DynState = type(
    "DynState",
    (rx.State,),
    {"__module__": __name__, "__annotations__": {"value": int}, "value": 3, "bump": _dyn_bump},
)

if IS_010:

    class ShadowState(PkgBaseState):
        # 0.10 allows a substate to redeclare an inherited var as its own.
        note: str = "shadow-default"

        @rx.event
        def set_shadow(self):
            self.note = "shadow-set"


def _fields_report() -> str:
    try:
        rep = {
            "backend_var_names(UserState)": backend_var_names(UserState),
            "own_backend_var_names(PkgBaseState)": own_backend_var_names(PkgBaseState),
            "own_backend_var_names(MixA)": own_backend_var_names(MixA),
            "__fields__ type": type(UserState.__fields__).__name__,
            "UserState.get_fields() keys": sorted(UserState.get_fields()),
            "MixA.event_handlers": sorted(MixA.event_handlers),
            "UserState.event_handlers": sorted(UserState.event_handlers),
            "PkgBaseState.event_handlers": sorted(PkgBaseState.event_handlers),
            "DynState.event_handlers": sorted(DynState.event_handlers),
            "PkgOtherState.dyn_added (class)": type(PkgOtherState.dyn_added).__name__,
        }
        return json.dumps(rep, indent=1)
    except Exception as e:  # noqa: BLE001
        return f"fields report error: {type(e).__name__}: {e}\n{traceback.format_exc()[-800:]}"


FIELDS_REPORT = _fields_report()
CLEAR_HANDLER = PkgBaseState.event_handlers["clear"]


@rx.page(route="/inherit")
def inherit() -> rx.Component:
    return rx.vstack(
        links(),
        rx.button("pkg add z", id="pkg_add", on_click=PkgBaseState.add("z")),
        rx.button("user add_twice", id="add_twice", on_click=UserState.add_twice),
        rx.button("user touch_other", id="touch_other", on_click=UserState.touch_other),
        rx.button("user read_values", id="read_values", on_click=UserState.read_values),
        rx.button("setvar extra", id="setvar", on_click=UserState.setvar("extra", "set-by-setvar")),
        rx.button("clear via event_handlers dict", id="clear_dict", on_click=CLEAR_HANDLER),
        rx.button("dyn bump", id="dyn_bump", on_click=DynState.bump),
        rx.text("items=", PkgBaseState.items.join(","), " n=", PkgBaseState.n_items, id="items"),
        rx.text("user.items=", UserState.items.join(","), " n=", UserState.n_items, id="user_items"),
        rx.text("extra=", UserState.extra, id="extra"),
        rx.text("note=", PkgBaseState.note, id="note"),
        rx.text("remote=", PkgOtherState.remote, " dyn_added=", PkgOtherState.dyn_added, id="remote"),
        rx.text("dyn=", DynState.value, id="dyn"),
        *(
            [
                rx.button("shadow set", id="shadow_set", on_click=ShadowState.set_shadow),
                rx.text("shadow.note=", ShadowState.note, " base.note=", PkgBaseState.note, id="shadow"),
            ]
            if IS_010
            else [rx.text("shadow n/a on 0.9", id="shadow")]
        ),
        rx.el.pre(FIELDS_REPORT, id="fields"),
    )


class ConstState(rx.State):
    """Class-level constants, the way reflex-dynoselect / reflex-clerk keep them."""

    _LABEL = "label-const"
    _SIZE = 16
    _OPTS = {"a": "A"}
    _CACHE: str | None = None
    shown: str = ""

    @classmethod
    def configure(cls, value: str) -> None:
        cls._CACHE = value  # package-style class-level "static" assignment

    @rx.event
    def show_instance(self):
        self.shown = f"{self._LABEL}|{self._SIZE}|{self._OPTS['a']}|cache={self._CACHE!r}"


ConstState.configure("configured-at-import")


def _classattr_report() -> str:
    try:
        return (
            f"class-level: _LABEL={ConstState._LABEL!r} _SIZE={ConstState._SIZE!r} "
            f"_OPTS={ConstState._OPTS!r} _CACHE={ConstState._CACHE!r}"
        )
    except Exception as e:  # noqa: BLE001
        return f"class-level error: {type(e).__name__}: {e}"


def _component_from_constant() -> rx.Component:
    try:
        return rx.text(ConstState._LABEL, id="from_const")
    except Exception as e:  # noqa: BLE001
        return rx.text(f"component-from-constant error: {type(e).__name__}: {str(e)[:300]}", id="from_const")


@rx.page(route="/classattr")
def classattr() -> rx.Component:
    return rx.vstack(
        links(),
        rx.text(_classattr_report(), id="classattr"),
        _component_from_constant(),
        rx.button("show instance", id="show_instance", on_click=ConstState.show_instance),
        rx.text("shown=", ConstState.shown, id="shown"),
    )


class BgState(rx.State):
    status: str = ""

    async def late_bg(self):
        async with self:
            self.status = "late_bg ran as background task"


_FIRST_IS_BG = BgState.late_bg.is_background  # first use of the handler
setattr(BgState.late_bg.fn, BACKGROUND_TASK_MARKER, True)  # marked after first use
_SECOND_IS_BG = BgState.late_bg.is_background


@rx.page(route="/background")
def background() -> rx.Component:
    return rx.vstack(
        links(),
        rx.text(f"is_background before={_FIRST_IS_BG} after-late-mark={_SECOND_IS_BG}", id="bg_flags"),
        rx.button("late bg", id="late_bg", on_click=BgState.late_bg),
        rx.text("status=", BgState.status, id="bg_status"),
    )


app = rx.App()
