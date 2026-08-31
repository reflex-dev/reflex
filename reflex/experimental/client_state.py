"""Deprecated `ClientStateVar` entry point.

The implementation moved to :mod:`reflex_base.client_state` and is exposed as
``rx.client_state``, whose signature is `client_state(default, *, name=None)`.
This module keeps the original signature working and is where the deprecation
notices live, so the new API carries none of them.
"""

from __future__ import annotations

from typing import Any

from reflex_base.client_state import ClientStateVar as ClientStateVar
from reflex_base.client_state import NoValue as NoValue
from reflex_base.utils import console

__all__ = ["ClientStateVar", "NoValue", "client_state"]


def client_state(
    var_name: str | None = None,
    default: Any = NoValue,
    global_ref: bool | Any = NoValue,
) -> ClientStateVar:
    """Create a client state var using the original argument order.

    Args:
        var_name: The name of the variable. Naming it makes the var global.
        default: The default value of the variable.
        global_ref: Formerly selected whether the state was app-wide. Scoping now
            follows from whether the var is named, so this is only honored to
            keep existing callers behaving as they did.

    Returns:
        The client state var.
    """
    console.deprecate(
        feature_name="rx._x.client_state",
        reason=(
            "Use rx.client_state(default, name=...) instead. Naming a var makes "
            "it global; an unnamed var is scoped to the component tree that "
            "first uses it, so `global_ref` is no longer needed."
        ),
        deprecation_version="0.9.9",
        removal_version="1.0",
    )
    # `global_ref=False` meant "anonymous": the name was never a store key, so
    # dropping it reproduces that exactly under the new scoping rules.
    if global_ref is not NoValue and not global_ref:
        var_name = None
    return ClientStateVar.create(default=default, name=var_name)
