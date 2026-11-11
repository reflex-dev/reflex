"""Compile-time behaviour of rx.form with TypedDict / FormData handlers (no server needed).

Run: cd $W && EXPECT_VENV=<venv> $SB/envs/<venv>/bin/python -I probe_form_compile.py
Each row prints OK/EXC with the exception type and first line of the message.
"""

from __future__ import annotations

import os
import warnings
from typing import TYPE_CHECKING, Annotated, Any, Generic, TypedDict, TypeVar

import reflex as rx
from typing_extensions import NotRequired, Required
from typing_extensions import TypedDict as TETypedDict

assert f"/envs/{os.environ.get('EXPECT_VENV', 'new')}/" in rx.__file__, rx.__file__
print("reflex", rx.__file__)

if TYPE_CHECKING:
    from decimal import Decimal  # only for type checking: unresolvable at runtime


class Signup(TypedDict):
    username: str
    email: str
    tags: list[str]
    agree: bool
    note: NotRequired[str]


class WithUnresolvable(TypedDict):
    amount: Decimal  # noqa: F821  (TYPE_CHECKING-only name under postponed annotations)
    name: str


class Bracketed(TypedDict):
    tags: list[str]


T = TypeVar("T")


class GBase(TETypedDict, Generic[T]):
    v: T


class GSpec(GBase[list[str]]):
    other: bool


class GPlainSub(GSpec):  # typing_extensions subclass keeps the type args
    pass


class S(rx.State):
    @rx.event
    def signup(self, form_data: Signup):
        pass

    @rx.event
    def unresolvable(self, form_data: WithUnresolvable):
        pass

    @rx.event
    def bracketed(self, form_data: Bracketed):
        pass

    @rx.event
    def gspec(self, form_data: GSpec):
        pass

    @rx.event
    def gplain(self, form_data: GPlainSub):
        pass

    @rx.event
    def plain(self, form_data: dict):
        pass

    @rx.event
    def wrong_type(self, form_data: int):
        pass

    @rx.event
    def listarg(self, form_data: list[str]):
        pass

    @rx.event
    def two_args(self, form_data: dict, other: str):
        pass

    x: str = ""

    @rx.event
    def set_x(self, v: str):
        self.x = v


try:
    FD = rx.form.FormData

    class S2(rx.State):
        @rx.event
        def fd(self, form_data: rx.form.FormData[str, str]):
            pass

        @rx.event
        def fd_opt(self, form_data: rx.form.FormData[str, str] | None):
            pass

        @rx.event
        def fd_bare(self, form_data: rx.form.FormData):
            pass

        @rx.event
        def fd_any(self, form_data: rx.form.FormData[str, Any]):
            pass

        @rx.event
        def fd_wrongk(self, form_data: rx.form.FormData[int, str]):
            pass

    HAS_FD = True
except AttributeError as e:
    print("rx.form.FormData not available:", e)
    HAS_FD = False


def row(label, fn):
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        try:
            fn()
            print(f"OK   {label}" + (f"  [{len(w)} py warnings: {[str(x.message)[:80] for x in w]}]" if w else ""))
        except Exception as e:  # noqa: BLE001
            msg = str(e).splitlines()
            print(f"EXC  {label}: {type(e).__name__}: {msg[0][:160]}" + (f" ... ({len(msg)} lines)" if len(msg) > 1 else ""))


row("TypedDict all required present", lambda: rx.form(rx.input(name="username"), rx.input(name="email"), rx.el.input(type="checkbox", name="tags", value="a"), rx.checkbox(name="agree"), on_submit=S.signup))
row("TypedDict missing 'email' (compile error expected)", lambda: rx.form(rx.input(name="username"), rx.el.input(type="checkbox", name="tags", value="a"), rx.checkbox(name="agree"), on_submit=S.signup))
row("TypedDict missing list+bool fields only", lambda: rx.form(rx.input(name="username"), rx.input(name="email"), on_submit=S.signup))
row("TypedDict 'email' provided by id only", lambda: rx.form(rx.input(name="username"), rx.input(id="email"), rx.el.input(type="checkbox", name="tags"), rx.checkbox(name="agree"), on_submit=S.signup))
row("TypedDict 'email' provided by radix form.field name (control has no name)", lambda: rx.form.root(rx.input(name="username"), rx.form.field(rx.form.control(rx.input(), as_child=True), name="email"), rx.el.input(type="checkbox", name="tags"), rx.checkbox(name="agree"), on_submit=S.signup))
row("TypedDict missing but form has an id (validation skipped)", lambda: rx.form(rx.input(name="username"), on_submit=S.signup, id="myform"))
row("TypedDict missing but a dynamic name (validation skipped)", lambda: rx.form(rx.input(name=S.router.page.path), on_submit=S.signup))
row("TypedDict missing but in foreach (dynamic)", lambda: rx.form(rx.foreach(["a", "b"], lambda x: rx.input(name=x)), on_submit=S.signup))
row("TypedDict missing + handler in a list chain", lambda: rx.form(rx.input(name="username"), on_submit=[S.signup, S.plain]))
row("TypedDict missing + lambda wrapper", lambda: rx.form(rx.input(name="username"), on_submit=lambda fd: S.signup(fd)))
row("TypedDict missing + controlled input provides it (DebounceInput name)", lambda: rx.form(rx.input(name="username"), rx.input(name="email", value=S.x, on_change=S.set_x), rx.el.input(type="checkbox", name="tags"), rx.checkbox(name="agree"), on_submit=S.signup))
row("TypedDict with TYPE_CHECKING-only field type (Decimal)", lambda: rx.form(rx.input(name="amount"), rx.input(name="name"), on_submit=S.unresolvable))
row("TypedDict list field filled by tags[] controls", lambda: rx.form(rx.input(name="tags[]"), on_submit=S.bracketed))
row("generic TypedDict specialization", lambda: rx.form(rx.input(name="v"), rx.checkbox(name="other"), on_submit=S.gspec))
row("generic TypedDict plain subclass (typing_extensions)", lambda: rx.form(rx.input(name="v"), rx.checkbox(name="other"), on_submit=S.gplain))
row("handler annotated int (wrong type)", lambda: rx.form(rx.input(name="x"), on_submit=S.wrong_type))
row("handler annotated list[str] (wrong type)", lambda: rx.form(rx.input(name="x"), on_submit=S.listarg))
row("handler with two params, no partial", lambda: rx.form(rx.input(name="x"), on_submit=S.two_args))
row("deprecation: id-only control + dict handler", lambda: rx.form(rx.input(id="only_id_1"), on_submit=S.plain))
row("deprecation: id-only control + NO form-data handler (no warning expected)", lambda: rx.form(rx.input(id="only_id_2"), on_submit=S.two_args("x", "y")))
row("deprecation: id-only control + prevent_default only", lambda: rx.form(rx.input(id="only_id_3")))
row("deprecation: id-only button/submit (no warning expected)", lambda: rx.form(rx.el.input(type="submit", id="only_id_4"), rx.button("go", id="only_id_5", type="submit"), on_submit=S.plain))
row("deprecation: id-only rx.upload inside form", lambda: rx.form(rx.upload(rx.text("drop"), id="upl1"), on_submit=S.plain))
row("deprecation: id-only disabled input (skipped)", lambda: rx.form(rx.input(id="only_id_6", disabled=True), on_submit=S.plain))
row("deprecation: id-only input in rx.cond", lambda: rx.form(rx.cond(S.router.page.path, rx.input(id="only_id_7"), rx.input(id="only_id_8")), on_submit=S.plain))
row("deprecation: id-only in memo'd child", lambda: rx.form(rx.vstack(rx.input(id="only_id_9"), rx.text(S.router.page.path)), on_submit=S.plain))
row("deprecation: same id twice (dedupe)", lambda: (rx.form(rx.input(id="only_id_1"), on_submit=S.plain), rx.form(rx.input(id="only_id_1"), on_submit=S.plain)))
if HAS_FD:
    row("FormData[str,str] handler", lambda: rx.form(rx.input(name="x"), on_submit=S2.fd))
    row("FormData | None handler", lambda: rx.form(rx.input(name="x"), on_submit=S2.fd_opt))
    row("bare FormData handler", lambda: rx.form(rx.input(name="x"), on_submit=S2.fd_bare))
    row("FormData[str,Any] handler", lambda: rx.form(rx.input(name="x"), on_submit=S2.fd_any))
    row("FormData[int,str] handler (wrong key type)", lambda: rx.form(rx.input(name="x"), on_submit=S2.fd_wrongk))
    from reflex_base.utils.form import FormData, transform_form_data, FORM_DATA_ENTRIES_KEY

    fd = FormData([("a", "1"), ("a", "2"), ("b", "x")])
    print("FormData repr", repr(fd), "len", len(fd), "a=", fd["a"], "getlist", fd.getlist("a"), "eq dict", fd == {"a": "2", "b": "x"}, "pickle-roundtrip", __import__("pickle").loads(__import__("pickle").dumps(fd)) == fd)
    try:
        fd.x = 1
    except AttributeError as e:
        print("immutable:", e)
    print("transform dict ann:", transform_form_data({FORM_DATA_ENTRIES_KEY: [["a", "1"], ["a", "2"], ["r[]", "1"], ["r[]", "2"]]}, dict))
    print("transform no ann:", transform_form_data({FORM_DATA_ENTRIES_KEY: [["a", "1"], ["a", "2"]]}, None))
    print("transform Bracketed:", transform_form_data({FORM_DATA_ENTRIES_KEY: [["tags[]", "1"], ["tags[]", "2"]]}, Bracketed))
    print("transform Signup empty:", transform_form_data({FORM_DATA_ENTRIES_KEY: []}, Signup))
    print("transform Signup bool strings:", [transform_form_data({FORM_DATA_ENTRIES_KEY: [["agree", v]]}, Signup)["agree"] for v in ("on", "true", "FALSE", " off ", "0", "1", "", "None", "nil", "yes")])
    for bad in ("not-a-list", 5, [["a"]], [[1, 2, 3]], {"a": 1}, None, [["a", "b"]]):
        try:
            print("envelope with", repr(bad), "->", transform_form_data({FORM_DATA_ENTRIES_KEY: bad}, dict))
        except Exception as e:  # noqa: BLE001
            print("envelope with", repr(bad), "-> EXC", type(e).__name__, e)
