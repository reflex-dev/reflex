"""Tests for the Vars that call ``reflex``, the API browser code reaches Reflex through."""

from typing import cast

import pytest
from reflex_base import js
from reflex_base.event import run_script
from reflex_base.utils.exceptions import EventFnArgMismatchError
from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import LiteralVar, Var, VarData

import reflex as rx

REFLEX_VAR_DATA = VarData(imports={"$/utils/reflex": [ImportVar(tag="reflex")]})


class JsState(rx.State):
    """A state whose handlers and vars the Vars are built with."""

    target: str = "search"

    @rx.event
    def save(self, value: int):
        """Take an argument.

        Args:
            value: The value.
        """

    @rx.event
    def save_pair(self, first: int, second: int):
        """Take two arguments.

        Args:
            first: The first value.
            second: The second value.
        """

    @rx.event
    def reset_all(self):
        """Take no arguments."""


def test_rx_js_is_reflex_base_js():
    """rx.js exposes exactly the public functions of reflex_base.js."""
    assert js.__all__ == ["add_events", "library", "ref"]
    assert [getattr(rx.js, name) for name in js.__all__] == [
        js.add_events,
        js.library,
        js.ref,
    ]


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


def test_add_events():
    """add_events compiles events, and handlers without arguments, to one dispatch."""
    name = JsState.get_full_name()
    dispatch = js.add_events(
        JsState.save(3), JsState.save_pair(1, 2), JsState.reset_all, rx.redirect("/x")
    )
    assert str(dispatch) == (
        "(reflex.addEvents(["
        f'(ReflexEvent("{name}.save", ({{ ["value"] : 3 }}), ({{  }}))), '
        f'(ReflexEvent("{name}.save_pair", ({{ ["first"] : 1, ["second"] : 2 }}), ({{  }}))), '
        f'(ReflexEvent("{name}.reset_all", ({{  }}), ({{  }}))), '
        '(ReflexEvent("_redirect", ({ ["path"] : "/x", ["external"] : false, '
        '["popup"] : false, ["replace"] : false }), ({  })))'
        "]))"
    )
    assert dispatch._get_all_var_data() == REFLEX_VAR_DATA
    assert str(js.add_events()) == "(reflex.addEvents([]))"


@pytest.mark.parametrize(
    ("event", "name"),
    [
        (JsState.save, "JsState.save"),
        (JsState.save_pair(1), "JsState.save_pair"),
    ],
)
def test_add_events_rejects_a_handler_missing_arguments(event, name: str):
    """A handler still missing arguments fails when add_events is built.

    Args:
        event: The handler or partial event.
        name: The handler's qualified name.
    """
    with pytest.raises(EventFnArgMismatchError) as error:
        js.add_events(JsState.reset_all, event)
    assert str(error.value) == (
        f"rx.js.add_events cannot dispatch {name}: the handler needs arguments, "
        "and add_events has none to pass it. Pass them where you add it, as in "
        f"rx.js.add_events({name}(...))."
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
