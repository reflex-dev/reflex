"""Tag to loop through a list of components."""

from __future__ import annotations

import dataclasses
import inspect
from typing import TYPE_CHECKING, Any, Callable, Iterable, Tuple, Type, Union, get_args

from reflex.components.tags.tag import Tag
from reflex.vars import LiteralArrayVar, Var, get_unique_variable_name

if TYPE_CHECKING:
    from reflex.components.component import Component


@dataclasses.dataclass()
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

    def get_iterable_var_type(self) -> Type:
        """Get the type of the iterable var.

        Returns:
            The type of the iterable var.
        """
        iterable = self.iterable
        try:
            if iterable._var_type.mro()[0] is dict:
                # Arg is a tuple of (key, value).
                return Tuple[get_args(iterable._var_type)]  # pyright: ignore [reportReturnType]
            elif iterable._var_type.mro()[0] is tuple:
                # Arg is a union of any possible values in the tuple.
                return Union[get_args(iterable._var_type)]  # pyright: ignore [reportReturnType]
            else:
                return get_args(iterable._var_type)[0]
        except Exception:
            return Any  # pyright: ignore [reportReturnType]

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
            if len(args) != 2:
                raise ValueError("The render function must take 2 arguments.")
            component = self.render_fn(arg, index)

        # Nested foreach components or cond must be wrapped in fragments.
        if isinstance(component, (Foreach, Cond)):
            component = Fragment.create(component)

        # If the component is a tuple, unpack and wrap it in a fragment.
        if isinstance(component, tuple):
            component = Fragment.create(*component)

        # Set the component key.
        if component.key is None:
            component.key = index

        return component
