"""Tests for reserved state names at class creation and dynamic registration."""

import pytest
from reflex_base.constants import RouteArgType
from reflex_base.utils.exceptions import StateValueError
from reflex_base.vars.base import EvenMoreBasicBaseState, LiteralVar, computed_var

import reflex as rx
from reflex.state import BaseState, _override_base_method
from reflex.vars import BaseStateMeta


@pytest.mark.parametrize("mixin", [False, True])
@pytest.mark.parametrize("base", [BaseState, rx.State])
def test_custom_state_metaclass(
    base: type[BaseState], mixin: bool, clean_registration_context
):
    """Support downstream metaclasses derived from the public BaseStateMeta.

    Args:
        base: The framework state class to extend.
        mixin: Whether the custom state is a mixin.
        clean_registration_context: An isolated state registry.
    """

    class CookieMeta(BaseStateMeta):
        """Add a field before the framework collects state declarations."""

        def __new__(mcs, name, bases, namespace, **kwargs):
            """Create a state with an injected field.

            Args:
                name: The class name.
                bases: The parent classes.
                namespace: The class declarations.
                **kwargs: Class creation options.

            Returns:
                The state class with the injected field.
            """
            namespace.setdefault("added_by_meta", "yes")
            return super().__new__(mcs, name, bases, namespace, **kwargs)

    class CookieState(base, mixin=mixin, metaclass=CookieMeta):
        x: int = 0

    assert type(base) is BaseStateMeta
    assert type(CookieState) is CookieMeta
    assert CookieState._mixin is mixin
    if mixin:

        class ConcreteState(CookieState, base):
            """Use the custom metaclass through state mixin inheritance."""

        state = ConcreteState
    else:
        state = CookieState
    assert type(state) is CookieMeta
    assert not state._mixin
    assert state.get_fields()["added_by_meta"].default_value() == "yes"
    assert "added_by_meta" in state.base_vars
    assert "x" in state.base_vars


@pytest.mark.parametrize("mixin", [False, True])
@pytest.mark.parametrize("reserved_name", ["get_fields", "__fields__"])
def test_custom_metaclass_reserved_name(
    reserved_name: str, mixin: bool, clean_registration_context
):
    """Validate declarations injected by downstream metaclasses.

    Args:
        reserved_name: The reserved name injected by the metaclass.
        mixin: Whether the custom state is a mixin.
        clean_registration_context: An isolated state registry.
    """

    class ReservedMeta(BaseStateMeta):
        """Inject a reserved field before delegating to the framework."""

        def __new__(mcs, name, bases, namespace, **kwargs):
            """Attempt to create a state with a reserved field.

            Args:
                name: The class name.
                bases: The parent classes.
                namespace: The class declarations.
                **kwargs: Class creation options.

            Returns:
                The state class if validation permits it.
            """
            namespace[reserved_name] = 7
            return super().__new__(mcs, name, bases, namespace, **kwargs)

    with pytest.raises(StateValueError, match=reserved_name):

        class ShadowState(rx.State, mixin=mixin, metaclass=ReservedMeta):
            """Reject the injected declaration before state initialization."""


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
