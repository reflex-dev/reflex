"""Where does rx.form.FormData[str, str] stop being a valid type form?"""
from typing import reveal_type

import reflex as rx
from reflex_base.utils.form import FormData
from reflex_components_radix.primitives.form import FormNamespace, form


def a(fd: rx.form.FormData[str, str]) -> None: ...
def b(fd: form.FormData[str, str]) -> None: ...
def c(fd: FormNamespace.FormData[str, str]) -> None: ...
def d(fd: FormData[str, str]) -> None: ...
def e(fd: rx.form.FormData) -> None: ...


reveal_type(rx.form)
reveal_type(rx.form.FormData)
reveal_type(rx.form(rx.input(name="x")))
reveal_type(rx.form.root(rx.input(name="x")))
reveal_type(rx.form.field(rx.form.label("x")))
