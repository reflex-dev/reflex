"""Deprecated `ClientStateVar` entry point.

The implementation moved to :mod:`reflex_base.client_state` and is exposed as
``rx.client_state``, whose signature is `client_state(default, *, name=None)`.
This module keeps the original signatures working and is where the deprecation
notices live, so the new API carries none of them.
"""

from __future__ import annotations

from typing import Any

from reflex_base.client_state import ClientStateVar as _ClientStateVar
from reflex_base.client_state import NoValue as NoValue
from reflex_base.client_state import _generate_name, _validate_name
from reflex_base.utils import console

__all__ = ["ClientStateVar", "NoValue", "client_state"]


def _deprecate(feature_name: str) -> None:
    """Warn that a legacy client state entry point was used.

    Args:
        feature_name: The legacy entry point.
    """
    console.deprecate(
        feature_name=feature_name,
        reason=(
            "Use rx.client_state(default, name=...) instead. Naming a var makes "
            "it global; an unnamed var is owned by the outermost page or "
            "`@rx.memo` that uses it, so `global_ref` is no longer needed."
        ),
        deprecation_version="0.11.0",
        removal_version="1.0",
    )


def _legacy_create(
    cls: type[_ClientStateVar],
    var_name: str | None,
    default: Any,
    global_ref: bool | Any,
) -> _ClientStateVar:
    """Create a var from the legacy ``(var_name, default, global_ref)`` arguments.

    ``global_ref`` defaults to true and an omitted ``var_name`` is generated, so
    a legacy var is global unless ``global_ref=False`` is passed, in which case
    its name is dropped and the var is scoped.

    Args:
        cls: The class to instantiate.
        var_name: The legacy name.
        default: The default value of the variable.
        global_ref: The legacy global flag, or ``NoValue`` when not given.

    Returns:
        The client state var.
    """
    if global_ref is not NoValue and not global_ref:
        return cls._create(default, _generate_name(), is_global=False)
    # A generated name is drawn from the same generator as scoped names, so the
    # two never collide; it is global only because the legacy API made it so.
    name = _generate_name() if var_name is None else _validate_name(var_name, "name")
    return cls._create(default, name, is_global=True)


class ClientStateVar(_ClientStateVar):
    """The promoted class, with ``create`` taking the original argument order."""

    # No new fields, so no dataclass decorator: ``slots=True`` would rebuild
    # the class and leave ``super()`` bound to the discarded one.
    __slots__ = ()

    @classmethod
    def create(  # pyright: ignore [reportIncompatibleMethodOverride]
        cls,
        var_name: str | None = None,
        default: Any = NoValue,
        global_ref: bool | Any = NoValue,
    ) -> _ClientStateVar:
        """Create a client state var using the original argument order.

        Args:
            var_name: The name of the variable. Naming it makes the var global.
            default: The default value of the variable.
            global_ref: Whether the state is app-wide. Scoping
                now follows from whether the var is named, so this is only honored
                to keep existing callers behaving as they did.

        Returns:
            The client state var.
        """
        _deprecate("ClientStateVar.create")
        return _legacy_create(cls, var_name, default, global_ref)


def client_state(
    var_name: str | None = None,
    default: Any = NoValue,
    global_ref: bool | Any = NoValue,
) -> _ClientStateVar:
    """Create a client state var using the original argument order.

    Args:
        var_name: The name of the variable. Naming it makes the var global.
        default: The default value of the variable.
        global_ref: Whether the state is app-wide. Scoping now
            follows from whether the var is named, so this is only honored to
            keep existing callers behaving as they did.

    Returns:
        The client state var.
    """
    _deprecate("rx._x.client_state")
    return _legacy_create(_ClientStateVar, var_name, default, global_ref)
