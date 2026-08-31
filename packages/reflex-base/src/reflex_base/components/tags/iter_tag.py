"""Tag to loop through a list of components."""

from __future__ import annotations

import dataclasses
import inspect
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING

from reflex_base.components.tags.tag import Tag
from reflex_base.constants import Dirs
from reflex_base.utils.imports import ImportVar
from reflex_base.utils.types import GenericType
from reflex_base.vars import LiteralArrayVar, Var, get_unique_variable_name
from reflex_base.vars.base import LiteralVar, VarData
from reflex_base.vars.sequence import _determine_value_of_array_index

if TYPE_CHECKING:
    from reflex_base.components.component import Component


_SCOPED_VALUE_IMPORT = {
    f"$/{Dirs.CLIENT_STATE_PATH}": [ImportVar(tag="useScopedValue")]
}


def scoped_loop_var(name: str, var_type: GenericType) -> Var:
    """Build a loop var that reads its value from the enclosing scope.

    A loop var used to render as nothing but the map callback's parameter, which
    broke the moment anything referencing it compiled into its own function -- an
    event handler hoisted into a ``useCallback``, or a subtree lifted into its own
    memo module (reflex-dev/reflex#3210). The loop now publishes the item and
    index by name around each rendered item, so a consumer reads them from
    context wherever the compiler puts it.

    The hook declares the *same* identifier as the map callback's parameter, on
    purpose. Hooks float to the top of whichever component they land in, so in
    the module that renders the loop itself the declaration sits above the
    ``.map`` and would read nothing -- the parameter shadows it for everything
    inside the callback, which is exactly the scope where the parameter is the
    real value. Anywhere else there is no parameter, and the context read wins.

    Args:
        name: The name the value is provided under.
        var_type: The type of the value.

    Returns:
        A Var carrying the hook that reads the value.
    """
    return Var(
        _js_expr=name,
        _var_type=var_type,
        _var_data=VarData(
            hooks={f"const {name} = useScopedValue({LiteralVar.create(name)!s})": None},
            imports=_SCOPED_VALUE_IMPORT,
        ),
    ).guess_type()


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
        return scoped_loop_var(self.index_var_name, int)

    def get_arg_var(self) -> Var:
        """Get the arg var for the tag (with curly braces).

        This is used to reference the arg var within the tag.

        Returns:
            The arg var.
        """
        return scoped_loop_var(self.arg_var_name, self.get_iterable_var_type())

    def render_component(self) -> Component:
        """Render the component.

        Returns:
            The rendered component.

        Raises:
            ValueError: If the render function takes more than 2 arguments.
            ValueError: If the render function doesn't return a component.
        """
        # Import here to avoid circular imports.
        from reflex_components_core.base.fragment import Fragment
        from reflex_components_core.core.cond import Cond
        from reflex_components_core.core.foreach import Foreach

        from reflex.compiler.compiler import _into_component_once

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

        return component
