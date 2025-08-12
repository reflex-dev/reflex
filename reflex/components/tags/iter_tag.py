"""Tag to loop through a list of components."""

from __future__ import annotations

import dataclasses
import inspect
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING

from reflex.components.tags.tag import Tag
from reflex.utils.types import GenericType
from reflex.vars import LiteralArrayVar, Var, get_unique_variable_name
from reflex.vars.sequence import _determine_value_of_array_index

if TYPE_CHECKING:
    from reflex.components.component import Component


@dataclasses.dataclass(frozen=True)
class IterTag(Tag):
    """An iterator tag."""

    # The var to iterate over.
    iterable: Var[Iterable] = dataclasses.field(
        default_factory=lambda: LiteralArrayVar.create([])
    )

    # The component render function for each item in the iterable.
    render_fn: Callable = dataclasses.field(default_factory=lambda: lambda x: x)

    # The name of the arg var.
    arg_var_name: str = dataclasses.field(default_factory=get_unique_variable_name)

    # The name of the index var.
    index_var_name: str = dataclasses.field(default_factory=get_unique_variable_name)

    def get_iterable_var_type(self) -> GenericType:
        """Get the type of the iterable var.

        Returns:
            The type of the iterable var.
        """
        return _determine_value_of_array_index(self.iterable._var_type)

    def get_index_var(self) -> Var:
        """Get the index var for the tag (with curly braces).

        This is used to reference the index var within the tag.

        Returns:
            The index var.
        """
        return Var(
            _js_expr=self.index_var_name,
            _var_type=int,
        ).guess_type()

    def get_arg_var(self) -> Var:
        """Get the arg var for the tag (with curly braces).

        This is used to reference the arg var within the tag.

        Returns:
            The arg var.
        """
        return Var(
            _js_expr=self.arg_var_name,
            _var_type=self.get_iterable_var_type(),
        ).guess_type()

    def get_index_var_arg(self) -> Var:
        """Get the index var for the tag (without curly braces).

        This is used to render the index var in the .map() function.

        Returns:
            The index var.
        """
        return Var(
            _js_expr=self.index_var_name,
            _var_type=int,
        ).guess_type()

    def get_arg_var_arg(self) -> Var:
        """Get the arg var for the tag (without curly braces).

        This is used to render the arg var in the .map() function.

        Returns:
            The arg var.
        """
        return Var(
            _js_expr=self.arg_var_name,
            _var_type=self.get_iterable_var_type(),
        ).guess_type()

    def render_component(self) -> Component:
        """Render the component.

        Raises:
            ValueError: If the render function takes more than 2 arguments.
            ValueError: If the render function doesn't return a component.

        Returns:
            The rendered component.
        """
        # Import here to avoid circular imports.
        from reflex.compiler.compiler import _into_component_once
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
            if len(args) != 2:
                msg = "The render function must take 2 arguments."
                raise ValueError(msg)
            component = self.render_fn(arg, index)

        # Nested foreach components or cond must be wrapped in fragments.
        if isinstance(component, (Foreach, Cond)):
            component = Fragment.create(component)

        component = _into_component_once(component)

        if component is None:
            msg = "The render function must return a component."
            raise ValueError(msg)

        # Set the component key.
        if component.key is None:
            component.key = index

        return component
