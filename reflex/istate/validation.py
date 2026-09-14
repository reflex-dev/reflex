"""Validate the framework namespace before constructing or extending a state."""

from functools import cache
from types import FunctionType
from typing import Any

from reflex_base.environment import environment
from reflex_base.utils import console
from reflex_base.utils.compat import annotations_from_namespace
from reflex_base.utils.exceptions import (
    EventHandlerShadowsBuiltInStateMethodError,
    StateValueError,
)
from reflex_base.vars.base import (
    BaseStateMeta,
    EvenMoreBasicBaseState,
    _linearize_bases,
)

_FIELD_MAP_NAMES = frozenset({"__fields__", "__own_fields__", "__inherited_fields__"})


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
    reason = (
        f"State name `{name}` is reserved by BaseState; use a different name instead."
    )
    if environment.REFLEX_STATE_ALLOW_RESERVED_NAMES.get():
        console.deprecate(
            feature_name="REFLEX_STATE_ALLOW_RESERVED_NAMES",
            reason=reason,
            deprecation_version="0.9.12",
            removal_version="1.0",
        )
        return
    msg = f"{reason} Set REFLEX_STATE_ALLOW_RESERVED_NAMES=1 temporarily to retain legacy behavior."
    raise StateValueError(msg)


class _StateMeta(BaseStateMeta):
    """Check state declarations before field collection and subclass initialization."""

    def __new__(
        cls,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        mixin: bool = False,
    ) -> type:
        """Construct a state after checking its declarations and Python mixins.

        Args:
            name: The class name.
            bases: The parent classes.
            namespace: The unmodified class namespace.
            mixin: Whether the class is a state mixin.

        Returns:
            The validated state class.
        """
        if any(isinstance(base, _StateMeta) for base in bases):
            seen = namespace.keys() | annotations_from_namespace(namespace).keys()
            for member in seen:
                _validate_state_name(member, namespace.get(member))
            for base in _linearize_bases(bases):
                if not isinstance(base, _StateMeta) and base not in (
                    EvenMoreBasicBaseState,
                    object,
                ):
                    if isinstance(base, BaseStateMeta):
                        # Model fields are inherited even when an earlier base
                        # masks their class attributes in the MRO.
                        for member in base.__own_fields__:
                            _validate_state_name(member)
                        seen.update(base.__own_fields__)
                    for member, value in vars(base).items():
                        if member not in seen and not (
                            isinstance(base, BaseStateMeta)
                            and (member in _FIELD_MAP_NAMES or member == "_mixin")
                        ):
                            _validate_state_name(member, value)
                seen.update(vars(base))
        return super().__new__(cls, name, bases, namespace, mixin=mixin)
