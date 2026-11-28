"""What a group of form controls shares: finding its items, and their state."""

from __future__ import annotations

import itertools
from collections.abc import Iterator
from typing import Any, TypeVar

from reflex_base.components.component import BaseComponent
from reflex_base.vars.base import LiteralVar, Var, VarData

T = TypeVar("T")

# Numbers the groups that are given no name of their own.
_names = itertools.count(1)


def group_name(name: Var | None, kind: str) -> Var:
    """Get the name the inputs of a group share.

    The browser takes radio buttons for one group by their name, so a group
    without one is given a name no other group of the app has.

    Args:
        name: The name the group was created with, or None.
        kind: What the group holds, such as ``radio``.

    Returns:
        The name of the inputs.
    """
    if name is not None:
        return name
    return LiteralVar.create(f"rx-{kind}-{next(_names)}")


def descendants(
    component: BaseComponent, kind: type[T], group: type | tuple[type, ...]
) -> Iterator[T]:
    """Find the items of a group below its root, at any depth.

    Args:
        component: The root of the group, or what is searched below it.
        kind: The class of the items.
        group: The class of a root: what is below another one is its own.

    Yields:
        Each item, in the order of the tree.
    """
    for child in component.children:
        if isinstance(child, kind):
            yield child
        if not isinstance(child, group):
            yield from descendants(child, kind, group)


def literal(value: Any) -> Any:
    """Read a value that is known while compiling.

    Args:
        value: A prop of a component.

    Returns:
        What a literal Var holds, or the value as given.
    """
    if isinstance(value, LiteralVar) and value._get_all_var_data() is None:
        return value._var_value
    return value


def either(first: Var | None, second: Var | None) -> Var | None:
    """Combine two flags, either of which may be left out.

    Args:
        first: A flag, such as whether a group is disabled.
        second: Another one, such as whether one of its items is.

    Returns:
        Whether one of them is set, or None when neither is given.
    """
    if first is None or second is None:
        return second if first is None else first
    one, other = literal(first), literal(second)
    if not isinstance(one, Var) and not isinstance(other, Var):
        return LiteralVar.create(bool(one or other))
    return Var(
        f"({first!s} || {second!s})",
        _var_type=bool,
        _var_data=VarData.merge(first._get_all_var_data(), second._get_all_var_data()),
    )


def is_value(selected: Var, value: Var | None) -> Var | bool:
    """Say whether an item is the one a group has selected.

    Args:
        selected: The value of the group.
        value: The value of the item.

    Returns:
        Whether they are equal: a bool when both are known while compiling.
    """
    if value is None:
        return False
    one, other = literal(selected), literal(value)
    if not isinstance(one, Var) and not isinstance(other, Var):
        return one == other
    return Var(
        f"({selected!s} === {value!s})",
        _var_type=bool,
        _var_data=VarData.merge(
            selected._get_all_var_data(), value._get_all_var_data()
        ),
    )
