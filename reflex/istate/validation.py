"""Validate the framework namespace before constructing or extending a state."""

from functools import cache
from types import FunctionType
from typing import Any

from reflex_base.utils.compat import annotations_from_namespace
from reflex_base.utils.exceptions import (
    EventHandlerShadowsBuiltInStateMethodError,
    StateValueError,
)
from reflex_base.vars.base import (
    BaseStateMeta,
    EvenMoreBasicBaseState,
    _linearize_bases,
    _set_state_declaration_validator,
)

_FIELD_MAP_NAMES = frozenset({"__fields__", "__own_fields__", "__inherited_fields__"})

# The state class whose subclasses are validated, set by `_install_state_validation`.
_validated_state_base: type | None = None


@cache
def _reserved_state_members() -> dict[str, Any]:
    """Return framework members, excluding state vars and Python protocols.

    Returns:
        Reserved names and their original descriptors, without invoking them.
    """
    # BaseState must exist before its namespace can be inspected.
    from reflex.state import BaseState

    members = {}
    for base in reversed(BaseState.__mro__[:-1]):
        namespace = vars(base)
        members.update(
            (name, namespace.get(name))
            for name in namespace.keys() | annotations_from_namespace(namespace).keys()
            if not name.startswith("__") or name in _FIELD_MAP_NAMES
        )
    for name, field in BaseState.__fields__.items():
        if field.is_var:
            members.pop(name, None)
    return members


def _validate_state_name(name: str, value: Any = None) -> None:
    """Reject declarations that replace framework methods or bookkeeping.

    Args:
        name: The declared or dynamically registered name.
        value: The raw class declaration, when available.

    Raises:
        StateValueError: If a declaration uses a reserved name.
        EventHandlerShadowsBuiltInStateMethodError: If a method overrides a builtin.
    """
    members = _reserved_state_members()
    if name not in members:
        return
    method = value.__func__ if isinstance(value, (classmethod, staticmethod)) else value
    if isinstance(method, FunctionType):
        if value is members[name] or getattr(method, "__override_base_method__", False):
            return
        msg = f"The event handler name `{name}` shadows a builtin State method; use a different name instead"
        raise EventHandlerShadowsBuiltInStateMethodError(msg)
    msg = f"State name `{name}` is reserved by BaseState; use a different name instead."
    raise StateValueError(msg)


def _validate_inherited_members(base: type, seen: set[str]) -> None:
    """Check the members a Python mixin or model base adds to a state.

    Args:
        base: A base class that is not itself a validated state.
        seen: Names an earlier base already provides in the MRO.
    """
    is_model = isinstance(base, BaseStateMeta)
    if is_model:
        # Model fields are inherited even when an earlier base masks their
        # class attributes in the MRO.
        for member in base.__own_fields__:
            _validate_state_name(member)
        seen.update(base.__own_fields__)
    for member, value in vars(base).items():
        if member not in seen and not (
            is_model and (member in _FIELD_MAP_NAMES or member == "_mixin")
        ):
            _validate_state_name(member, value)


def _validate_state_declaration(
    bases: tuple[type, ...], namespace: dict[str, Any]
) -> None:
    """Check a state's declarations and Python mixins before it is constructed.

    Classes that do not inherit from the validated state base, such as plain
    models built on the same metaclass, keep their own namespace.

    Args:
        bases: The parent classes of the class being created.
        namespace: The unmodified class namespace.
    """
    base_state = _validated_state_base
    if base_state is None or not any(issubclass(base, base_state) for base in bases):
        return
    seen = namespace.keys() | annotations_from_namespace(namespace).keys()
    for member in seen:
        _validate_state_name(member, namespace.get(member))
    for base in _linearize_bases(bases):
        if (
            not issubclass(base, base_state)
            and base is not EvenMoreBasicBaseState
            and base is not object
        ):
            _validate_inherited_members(base, seen)
        seen.update(vars(base))


def _install_state_validation(base_state: type) -> None:
    """Validate every state declared after this call.

    Args:
        base_state: The state class whose subclasses must be validated.
    """
    global _validated_state_base
    _validated_state_base = base_state
    _set_state_declaration_validator(_validate_state_declaration)
