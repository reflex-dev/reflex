"""Tag to loop through a list of components."""
from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Callable, List, Tuple, Type, Union, get_args

from reflex.components.tags.tag import Tag
from reflex.vars import BaseVar, Var

if TYPE_CHECKING:
    from reflex.components.component import Component


class IterTag(Tag):
    """An iterator tag."""

    # The var to iterate over.
    iterable: Var[List]

    # The component render function for each item in the iterable.
    render_fn: Callable

    # The name of the arg var.
    arg_var_name: str

    # The name of the index var.
    index_var_name: str

    def get_iterable_var_type(self) -> Type:
        """Get the type of the iterable var.

        Returns:
            The type of the iterable var.
        """
        try:
            if self.iterable._var_type.mro()[0] == dict:
                # Arg is a tuple of (key, value).
                return Tuple[get_args(self.iterable._var_type)]  # type: ignore
            elif self.iterable._var_type.mro()[0] == tuple:
                # Arg is a union of any possible values in the tuple.
                return Union[get_args(self.iterable._var_type)]  # type: ignore
            else:
                return get_args(self.iterable._var_type)[0]
        except Exception:
            return Any

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

    def get_arg_var(self) -> Var:
        """Get the arg var for the tag (with curly braces).

        This is used to reference the arg var within the tag.

        Returns:
            The arg var.
        """
        return BaseVar(
            _var_name=self.arg_var_name,
            _var_type=self.get_iterable_var_type(),
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

    def get_arg_var_arg(self) -> Var:
        """Get the arg var for the tag (without curly braces).

        This is used to render the arg var in the .map() function.

        Returns:
            The arg var.
        """
        return BaseVar(
            _var_name=self.arg_var_name,
            _var_type=self.get_iterable_var_type(),
            _var_is_local=True,
        )

    def render_component(self) -> Component:
        """Render the component.

        Returns:
            The rendered component.
        """
        # Import here to avoid circular imports.
        from reflex.components.base.fragment import Fragment
        from reflex.components.core.cond import Cond
        from reflex.components.core.foreach import Foreach

        # Get the render function arguments.
        args = inspect.getfullargspec(self.render_fn).args
        arg = self.get_arg_var()
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
