"""Tests for reflex_base.vars.special hook-backed vars."""

from typing import Any

from reflex_base.components.component import Component
from reflex_base.utils.imports import ImportVar
from reflex_base.vars.number import NumberVar
from reflex_base.vars.sequence import StringVar
from reflex_base.vars.special import use_hook_var, use_id


class HookComponent(Component):
    """A minimal component for asserting hook var hoisting."""

    library = "test-lib"

    tag = "HookComponent"


def test_use_hook_var_var_data():
    """use_hook_var carries the hook statement and its import in VarData."""
    v = use_hook_var(library="some-lib", hook="useThing")
    assert v._var_type is Any
    vd = v._get_all_var_data()
    assert vd is not None
    hook_alias = f"useThing_{v!s}"
    assert vd.hooks == (f"const {v!s} = {hook_alias}();",)
    assert vd.imports == (("some-lib", (ImportVar(tag="useThing", alias=hook_alias),)),)


def test_use_hook_var_guesses_var_type():
    """The returned Var is downcast to the class matching _var_type."""
    count = use_hook_var(library="some-lib", hook="useCount", _var_type=int)
    assert isinstance(count, NumberVar)
    assert count._var_type is int

    maybe = use_hook_var(library="some-lib", hook="useMaybe", _var_type=int | None)
    assert maybe._var_type == (int | None)


def test_use_hook_var_names_are_unique():
    """Each call binds the hook value to a fresh variable name."""
    names = {str(use_hook_var(library="some-lib", hook="useThing")) for _ in range(5)}
    assert len(names) == 5


def test_same_named_hook_imports_are_aliased():
    """Same-named hooks from different libraries do not collide in JS imports."""
    first = use_hook_var(library="first-lib", hook="useThing")
    second = use_hook_var(library="second-lib", hook="useThing")
    first_alias = f"useThing_{first!s}"
    second_alias = f"useThing_{second!s}"
    first_var_data = first._get_all_var_data()
    second_var_data = second._get_all_var_data()

    assert first_alias != second_alias
    assert first_var_data is not None
    assert second_var_data is not None
    assert first_var_data.imports == (
        ("first-lib", (ImportVar(tag="useThing", alias=first_alias),)),
    )
    assert second_var_data.imports == (
        ("second-lib", (ImportVar(tag="useThing", alias=second_alias),)),
    )


def test_use_id():
    """use_id returns a str Var bound to React's useId hook."""
    v = use_id()
    assert isinstance(v, StringVar)
    assert v._var_type is str
    vd = v._get_all_var_data()
    assert vd is not None
    hook_alias = f"useId_{v!s}"
    assert vd.hooks == (f"const {v!s} = {hook_alias}();",)
    assert vd.imports == (("react", (ImportVar(tag="useId", alias=hook_alias),)),)


def test_hook_var_hoisted_into_component():
    """A component using a hook var renders the hook and pulls its import."""
    v = use_id()
    comp = HookComponent.create(id=v)
    hook_alias = f"useId_{v!s}"
    assert f"const {v!s} = {hook_alias}();" in comp._get_all_hooks()
    assert ImportVar(tag="useId", alias=hook_alias) in comp._get_all_imports()["react"]
    assert comp.render()["props"] == [f"id:{v!s}"]
