"""Tag to loop through a list of components."""
from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Callable, List

from reflex.components.tags.tag import Tag
from reflex.vars import BaseVar, Var

if TYPE_CHECKING:
    from reflex.components.component import Component


INDEX_VAR = "i"


class IterTag(Tag):
    """An iterator tag."""

    # The var to iterate over.
    iterable: Var[List]

    # The component render function for each item in the iterable.
    render_fn: Callable

    @staticmethod
    def get_index_var() -> Var:
        """Get the index var for the tag.

        Returns:
            The index var.
        """
        return BaseVar(
            name=INDEX_VAR,
            type_=int,
        )

    @staticmethod
    def get_index_var_arg() -> Var:
        """Get the index var for the tag.

        Returns:
            The index var.
        """
        return BaseVar(
            name=INDEX_VAR,
            type_=int,
            is_local=True,
        )

    @staticmethod
    def render_component(render_fn: Callable, arg: Var) -> Component:
        """Render the component.

        Args:
            render_fn: The render function.
            arg: The argument to pass to the render function.

        Returns:
            The rendered component.
        """
        # Import here to avoid circular imports.
        from reflex.components.layout.cond import Cond
        from reflex.components.layout.foreach import Foreach
        from reflex.components.layout.fragment import Fragment

        # Get the render function arguments.
        args = inspect.getfullargspec(render_fn).args
        index = IterTag.get_index_var()

        if len(args) == 1:
            # If the render function doesn't take the index as an argument.
            component = render_fn(arg)
        else:
            # If the render function takes the index as an argument.
            assert len(args) == 2
            component = render_fn(arg, index)

        # Nested foreach components or cond must be wrapped in fragments.
        if isinstance(component, (Foreach, Cond)):
            component = Fragment.create(component)

        # Set the component key.
        if component.key is None:
            component.key = index

        return component
