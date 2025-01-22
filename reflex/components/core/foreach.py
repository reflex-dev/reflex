"""Create a list of components from an iterable."""

from __future__ import annotations

from typing import Callable, Iterable

from reflex.vars.base import LiteralVar, Var
from reflex.vars.object import ObjectVar
from reflex.vars.sequence import ArrayVar


class ForeachVarError(TypeError):
    """Raised when the iterable type is Any."""


class ForeachRenderError(TypeError):
    """Raised when there is an error with the foreach render function."""


def foreach(
    iterable: Var[Iterable] | Iterable,
    render_fn: Callable,
) -> Var:
    """Create a foreach component.

    Args:
        iterable: The iterable to create components from.
        render_fn: A function from the render args to the component.

    Returns:
        The foreach component.

    Raises:
        ForeachVarError: If the iterable is of type Any.
    """
    iterable = LiteralVar.create(iterable).guess_type()
    if isinstance(iterable, ObjectVar):
        iterable = iterable.items()

    if not isinstance(iterable, ArrayVar):
        raise ForeachVarError(
            f"Could not foreach over var `{iterable!s}` of type {iterable._var_type!s}. "
            "(If you are trying to foreach over a state var, add a type annotation to the var). "
            "See https://reflex.dev/docs/library/dynamic-rendering/foreach/"
        )

    return iterable.foreach(render_fn)


class Foreach:
    """Create a list of components from an iterable."""

    create = staticmethod(foreach)
