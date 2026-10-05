"""Component with string-based tuple return annotations on event handlers.

This module tests:
- figure_out_return_type with string-based "tuple[...]" annotation
- The string parsing path for event handler signatures
- Empty tuple[()], single arg tuple[str], multi-arg tuple[str, int]
"""

from reflex_base.components.component import Component, field
from reflex_base.event import EventHandler
from reflex_base.vars.base import Var


def on_empty_handler() -> "tuple[()]":
    """Handler returning empty tuple.

    Returns:
        An empty tuple.
    """
    return ()


def on_string_handler(value: Var[str]) -> "tuple[Var[str]]":
    """Handler returning a single string arg.

    Args:
        value: The string value from the event.

    Returns:
        A tuple containing the string value.
    """
    return (value,)


def on_multi_handler(name: Var[str], age: Var[int]) -> "tuple[Var[str], Var[int]]":
    """Handler returning multiple args.

    Args:
        name: The name from the event.
        age: The age from the event.

    Returns:
        A tuple containing the name and age.
    """
    return (name, age)


class StringAnnotationComponent(Component):
    """A component with string-annotated event handlers."""

    value: Var[str]

    on_empty: EventHandler[on_empty_handler] = field(
        doc="Fires with no args.",
    )

    on_string: EventHandler[on_string_handler] = field(
        doc="Fires with a string.",
    )

    on_multi: EventHandler[on_multi_handler] = field(
        doc="Fires with name and age.",
    )
