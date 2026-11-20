"""Tests for the script environment Var."""

from typing import cast

from reflex_base.event import EventSpec, run_script
from reflex_base.js import env
from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import LiteralVar, Var, VarData

import reflex as rx

ENV_VAR_DATA = VarData(
    imports={"$/utils/script_env": [ImportVar(tag="env", alias="__reflexEnv")]}
)


class EnvState(rx.State):
    """A state whose handlers and vars the env Var is built with."""

    target: str = "search"

    @rx.event
    def save(self, value: int):
        """Take an argument.

        Args:
            value: The value.
        """

    @rx.event
    def reset_all(self):
        """Take no arguments."""


def test_env_renders_under_its_alias_with_its_import():
    """The env Var renders under its alias and imports it from script_env."""
    assert str(env) == "__reflexEnv"
    assert env._get_all_var_data() == ENV_VAR_DATA
    assert rx.js.env is env


def test_refs_and_ref():
    """Refs and ref() render on the alias and keep the var data of their arguments."""
    assert str(env.refs) == "__reflexEnv.refs"
    assert env.refs._get_all_var_data() == ENV_VAR_DATA
    assert str(env.ref("search")) == '(__reflexEnv.ref("search"))'
    target = cast(Var[str], EnvState.target)
    ref = env.ref(target)
    assert str(ref) == f"(__reflexEnv.ref({target!s}))"
    assert ref._get_all_var_data() == VarData.merge(
        ENV_VAR_DATA, target._get_all_var_data()
    )


def test_add_events_takes_specs_and_argless_handlers():
    """add_events compiles event specs, and handlers without arguments, to events."""
    name = EnvState.get_full_name()
    assert str(env.add_events(EnvState.save(3), EnvState.reset_all)) == (
        "(__reflexEnv.addEvents(["
        f'(ReflexEvent("{name}.save", ({{ ["value"] : 3 }}), ({{  }}))), '
        f'(ReflexEvent("{name}.reset_all", ({{  }}), ({{  }})))'
        "]))"
    )


def test_library():
    """library() renders a call on the alias."""
    assert str(env.library("react")) == '(__reflexEnv.library("react"))'


def test_run_script_carries_the_import_into_the_page():
    """A script built on env carries the env import into the page that uses it."""
    spec = run_script(env.ref("search"))
    assert isinstance(spec, EventSpec)
    literal = LiteralVar.create(spec)
    assert str(literal) == (
        '(ReflexEvent("_call_function", ({ ["function"] : '
        '(() => (__reflexEnv.ref("search"))), ["callback"] : null }), ({  })))'
    )
    assert literal._get_all_var_data() == ENV_VAR_DATA
