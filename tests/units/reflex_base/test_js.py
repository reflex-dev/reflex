"""Tests for the Vars that call ``reflex``, the API browser code reaches Reflex through."""

from typing import cast

from reflex_base import js
from reflex_base.event import run_script
from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import LiteralVar, Var, VarData

import reflex as rx

REFLEX_VAR_DATA = VarData(imports={"$/utils/reflex": [ImportVar(tag="reflex")]})


class JsState(rx.State):
    """A state whose var the Vars are built with."""

    target: str = "search"


def test_rx_js_is_reflex_base_js():
    """rx.js exposes exactly the public functions of reflex_base.js."""
    assert js.__all__ == ["library", "ref"]
    assert [getattr(rx.js, name) for name in js.__all__] == [js.library, js.ref]


def test_ref():
    """ref() calls reflex.ref, keeps its argument's var data, and reads current."""
    search = js.ref("search")
    assert str(search) == '(reflex.ref("search"))'
    assert search._get_all_var_data() == REFLEX_VAR_DATA
    assert str(search.current.value) == '(reflex.ref("search"))?.["current"]?.["value"]'

    target = cast(Var[str], JsState.target)
    ref = js.ref(target)
    assert str(ref) == f"(reflex.ref({target!s}))"
    assert ref._get_all_var_data() == VarData.merge(
        REFLEX_VAR_DATA, target._get_all_var_data()
    )


def test_library():
    """library() calls reflex.library."""
    react = js.library("react")
    assert str(react) == '(reflex.library("react"))'
    assert react._get_all_var_data() == REFLEX_VAR_DATA


def test_run_script_carries_the_import_into_the_page():
    """A script built on reflex carries the reflex import into the page that uses it."""
    literal = LiteralVar.create(run_script(js.ref("search")))
    assert str(literal) == (
        '(ReflexEvent("_call_function", ({ ["function"] : '
        '(() => (reflex.ref("search"))), ["callback"] : null }), ({  })))'
    )
    assert literal._get_all_var_data() == REFLEX_VAR_DATA
