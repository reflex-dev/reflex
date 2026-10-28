"""Deprecated `ClientStateVar` entry point.

The implementation moved to :mod:`reflex_base.client_state` and is exposed as
``rx.client_state``, whose signature is `client_state(default, *, name=None)`.
This module keeps the original signatures working and is where the deprecation
notices live, so the new API carries none of them.
"""

from __future__ import annotations

from typing import Any

from reflex_base.client_state import _DEFAULT_NAME_PREFIX, _name_counter
from reflex_base.client_state import ClientStateVar as _ClientStateVar
from reflex_base.client_state import NoValue as NoValue
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
            "it global; an unnamed var is scoped to the component tree that "
            "first uses it, so `global_ref` is no longer needed."
        ),
        deprecation_version="0.10.0",
        removal_version="1.0",
    )


def _legacy_name(var_name: str | None, global_ref: bool | Any) -> str | None:
    """Map the legacy ``(var_name, global_ref)`` pair onto the naming rules.

    ``global_ref`` defaults to true and an omitted ``var_name`` is generated, so
    a legacy var is global unless ``global_ref=False`` is passed, in which case
    its name is dropped and the var is scoped.

    Args:
        var_name: The legacy name.
        global_ref: The legacy global flag, or ``NoValue`` when not given.

    Returns:
        The name to create the var with: ``None`` scopes it, anything else
        makes it global.
    """
    if global_ref is not NoValue and not global_ref:
        return None
    if var_name is None:
        # The shared counter keeps a generated global name from colliding with
        # a generated scoped one.
        return f"{_DEFAULT_NAME_PREFIX}{next(_name_counter)}"
    return var_name


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
        return super().create(default, name=_legacy_name(var_name, global_ref))


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
    return _ClientStateVar.create(default, name=_legacy_name(var_name, global_ref))
