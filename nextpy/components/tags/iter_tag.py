"""Tag to loop through a list of components."""
from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Callable, List

from nextpy.components.tags.tag import Tag
from nextpy.core.vars import BaseVar, Var

if TYPE_CHECKING:
    from nextpy.components.component import Component


class IterTag(Tag):
    """An iterator tag."""

    # The var to iterate over.
    iterable: Var[List]

    # The component render function for each item in the iterable.
    render_fn: Callable

    # The name of the index var.
    index_var_name: str = "i"

    def get_index_var(self) -> Var:
        """Get the index var for the tag (with curly braces).

        This is used to reference the index var within the tag.

        Returns:
            The index var.
        """
        return BaseVar(
            _var_name=self.index_var_name,
            _var_type=int,
        )

    def get_index_var_arg(self) -> Var:
        """Get the index var for the tag (without curly braces).

        This is used to render the index var in the .map() function.
        Returns:
            The index var.
        """
        return BaseVar(
            _var_name=self.index_var_name,
            _var_type=int,
            _var_is_local=True,
        )

    def render_component(self, arg: Var) -> Component:
        """Render the component.

        Args:
            arg: The argument to pass to the render function.

        Returns:
            The rendered component.
        """
        # Import here to avoid circular imports.
        from nextpy.components.layout.cond import Cond
        from nextpy.components.layout.foreach import Foreach
        from nextpy.components.layout.fragment import Fragment

        # Get the render function arguments.
        args = inspect.getfullargspec(self.render_fn).args
        index = self.get_index_var()

        if len(args) == 1:
            # If the render function doesn't take the index as an argument.
            component = self.render_fn(arg)
        else:
            # If the render function takes the index as an argument.
            assert len(args) == 2
            component = self.render_fn(arg, index)

        # Nested foreach components or cond must be wrapped in fragments.
        if isinstance(component, (Foreach, Cond)):
            component = Fragment.create(component)

        # Set the component key.
        if component.key is None:
            component.key = index

        return component
