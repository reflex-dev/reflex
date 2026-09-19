"""Tests for reserved state names at class creation and dynamic registration."""

from typing import Any

import pytest
from reflex_base.constants import RouteArgType
from reflex_base.utils.exceptions import StateValueError
from reflex_base.vars.base import (
    BaseStateMeta,
    EvenMoreBasicBaseState,
    LiteralVar,
    computed_var,
)

from reflex.state import BaseState, State, _override_base_method


@pytest.mark.parametrize(
    "name",
    [
        "_get_was_touched",
        "_update_was_touched",
        "_was_touched",
        "dirty_vars",
        "get_fields",
        "get_full_name",
        "backend_vars",
        "__fields__",
        "setvar",
    ],
)
@pytest.mark.parametrize("annotated", [False, True])
def test_reserved_state_var(name: str, annotated: bool, clean_registration_context):
    """Reject framework names before state initialization can call them.

    Args:
        name: The reserved member to shadow.
        annotated: Whether to explicitly annotate the variable.
        clean_registration_context: An isolated state registry.
    """
    namespace = {"__module__": __name__, "__qualname__": "ShadowState", name: 7}
    if annotated:
        namespace["__annotations__"] = {name: int}
    with pytest.raises(StateValueError, match=name):
        type("ShadowState", (BaseState,), namespace)


def test_reserved_annotation_only(clean_registration_context):
    """Reject a reserved var even when no default is declared.

    Args:
        clean_registration_context: An isolated state registry.
    """
    with pytest.raises(StateValueError, match="_get_was_touched"):

        class ShadowState(BaseState):
            _get_was_touched: int


@pytest.mark.parametrize("state_mixin", [False, True])
def test_reserved_mixin_var(state_mixin: bool, clean_registration_context):
    """Reject collisions from both ordinary Python mixins and state mixins.

    Args:
        state_mixin: Whether the mixin subclasses BaseState.
        clean_registration_context: An isolated state registry.
    """
    with pytest.raises(StateValueError, match="_update_was_touched"):
        mixin = type(
            "Mixin",
            (BaseState,) if state_mixin else (),
            {"__module__": __name__, "_update_was_touched": 7},
            **({"mixin": True} if state_mixin else {}),
        )
        type("MixedState", (mixin, BaseState), {"__module__": __name__})


@pytest.mark.parametrize("name", ["_get_was_touched", "get_fields"])
def test_reserved_computed_var(name: str, clean_registration_context):
    """Reject computed vars that replace framework methods.

    Args:
        name: The reserved method to replace.
        clean_registration_context: An isolated state registry.
    """

    def value(self) -> int:
        """Return a constant computed value."""
        return 7

    value.__name__ = name
    with pytest.raises(StateValueError, match=name):
        type(
            "ComputedState",
            (BaseState,),
            {"__module__": __name__, name: computed_var(value)},
        )


@pytest.mark.parametrize("registration", ["var", "route", "event", "field"])
def test_dynamic_reserved_name(registration: str, clean_registration_context):
    """Reject dynamic collisions before any field or event map is changed.

    Args:
        registration: The dynamic registration path to exercise.
        clean_registration_context: An isolated state registry.
    """

    class DynamicState(BaseState):
        """State receiving a dynamic declaration."""

    fields = dict(DynamicState.get_fields())
    with pytest.raises(StateValueError, match="get_state"):
        if registration == "var":
            DynamicState.add_var("get_state", int, 7)
        elif registration == "route":
            DynamicState.setup_dynamic_args({"get_state": RouteArgType.SINGLE})
        elif registration == "event":
            DynamicState._add_event_handler("get_state", lambda self: None)
        else:
            DynamicState.add_field("get_state", LiteralVar.create(7), 7)
    assert DynamicState.get_fields() == fields
    assert "get_state" not in DynamicState.vars
    assert "get_state" not in DynamicState.event_handlers
    assert "get_state" not in DynamicState.__dict__


def test_user_vars_and_marked_override(clean_registration_context):
    """Keep normal vars, inherited vars, and explicitly marked method overrides.

    Args:
        clean_registration_context: An isolated state registry.
    """

    class Parent(BaseState):
        value: int = 1
        _backend: int = 2

    class Child(Parent):
        @_override_base_method
        def get_value(self, key: str):
            """Return a value through a supported framework override."""
            return f"override:{key}"

    parent = Parent()
    child = parent.substates[Child.get_name()]
    assert isinstance(child, Child)
    assert child.value == 1
    assert child._backend == 2
    assert child.get_value("value") == "override:value"


def test_non_state_models_keep_their_namespace():
    """Do not reserve Reflex state names on unrelated base models."""

    class Model(EvenMoreBasicBaseState):
        get_state: int = 7

    assert Model().get_state == 7


@pytest.mark.parametrize("name", ["get_fields", "_get_was_touched"])
@pytest.mark.parametrize("state_first", [False, True])
def test_reserved_model_mixin(name: str, state_first: bool, clean_registration_context):
    """Reject inherited model fields before the field collector sees them.

    Args:
        name: The framework name declared as a model field.
        state_first: Whether BaseState precedes the model in the MRO.
        clean_registration_context: An isolated state registry.
    """
    model = type("Model", (EvenMoreBasicBaseState,), {"__module__": __name__, name: 7})
    bases = (BaseState, model) if state_first else (model, BaseState)
    with pytest.raises(StateValueError, match=name):
        type("MixedState", bases, {"__module__": __name__})


def test_reserved_descriptor(clean_registration_context):
    """Reject a descriptor without executing its class access behavior.

    Args:
        clean_registration_context: An isolated state registry.
    """

    class Descriptor:
        def __get__(self, instance, owner):
            """Fail if validation invokes this descriptor."""
            pytest.fail("Reserved descriptor was evaluated")

    with pytest.raises(StateValueError, match="get_fields"):
        type(
            "DescriptorState",
            (BaseState,),
            {"__module__": __name__, "get_fields": Descriptor()},
        )


class _CookieMeta(BaseStateMeta):
    """A downstream-style metaclass that injects fields into the declaration."""

    def __new__(
        cls, name: str, bases: tuple[type, ...], namespace: dict[str, Any], **kwargs
    ):
        """Add an annotated backend var before the state is constructed.

        Args:
            name: The class name.
            bases: The parent classes.
            namespace: The class namespace.
            **kwargs: Class creation keywords, e.g. `mixin`.

        Returns:
            The new state class.
        """
        namespace.setdefault("__annotations__", {})["_injected"] = str
        namespace["_injected"] = "by the metaclass"
        return super().__new__(cls, name, bases, namespace, **kwargs)


def test_state_metaclass_is_base_state_meta():
    """Keep the exported `BaseStateMeta` as the metaclass of every state."""
    assert type(BaseState) is BaseStateMeta
    assert type(State) is BaseStateMeta


@pytest.mark.parametrize("mixin", [False, True])
def test_custom_state_metaclass(mixin: bool, clean_registration_context):
    """Allow a `BaseStateMeta` subclass as the metaclass of a state.

    Args:
        mixin: Whether the state is declared as a state mixin.
        clean_registration_context: An isolated state registry.
    """

    class CustomState(State, mixin=mixin, metaclass=_CookieMeta):
        value: int = 1

    assert type(CustomState) is _CookieMeta
    assert CustomState._mixin is mixin
    assert CustomState.__fields__["_injected"].default == "by the metaclass"
    assert CustomState.__fields__["value"].default == 1


def test_custom_state_metaclass_validates_reserved_names(clean_registration_context):
    """Keep rejecting reserved names declared through a custom metaclass.

    Args:
        clean_registration_context: An isolated state registry.
    """
    with pytest.raises(StateValueError, match="get_fields"):

        class ShadowState(BaseState, metaclass=_CookieMeta):
            get_fields: int = 7
