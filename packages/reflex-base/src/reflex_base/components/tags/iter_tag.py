"""Tag to loop through a list of components."""

from __future__ import annotations

import dataclasses
import functools
import inspect
import logging
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING

from reflex_base.components.tags.tag import CommonTag
from reflex_base.environment import environment
from reflex_base.utils.types import GenericType
from reflex_base.vars import LiteralArrayVar, Var, VarData, get_unique_variable_name
from reflex_base.vars.sequence import _determine_value_of_array_index

if TYPE_CHECKING:
    from reflex_base.components.component import Component

logger = logging.getLogger(__name__)


@functools.cache
def _loop_var_data(name: str) -> VarData:
    """Get the var data that makes a loop variable name itself as a dependency.

    Every var built from the loop variable carries the name, so a generated
    function that reads it can receive it as a prop.

    Args:
        name: The JavaScript name of the loop variable.

    Returns:
        The var data, shared by every var with this name.
    """
    return VarData(deps=[Var(_js_expr=name)])


@dataclasses.dataclass(frozen=True)
class IterTag(CommonTag):
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
            _var_data=_loop_var_data(self.index_var_name),
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
            _var_data=_loop_var_data(self.arg_var_name),
        ).guess_type()

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

        # Set the component key.
        if component.key is None:
            self._warn_index_key(component)
            component.key = index

        return component

    def _warn_index_key(self, component: Component) -> None:
        """Warn once when an item keyed by its index has hooks of its own.

        Lifecycle events and added hooks belong to one rendered instance, which
        React matches to an item by key. Keyed by index, they follow the
        position, so after a removal ``on_unmount`` names the item at the end.
        Only a frontend compile warns, not a process that only evaluates pages.

        Args:
            component: The rendered item, which has no key.
        """
        if environment.REFLEX_SKIP_COMPILE.get():
            return
        from reflex.compiler.plugins.memoize import _subtree_has_instance_hooks

        if not _subtree_has_instance_hooks(component):
            return
        logger.warning(
            f"The rx.foreach over `{self.iterable!s}` renders a"
            f" {type(component).__name__} with lifecycle events or hooks but no"
            " key, so each item is keyed by its index: after an item is removed"
            " or moved, its hooks run for the item now at that position. Set a"
            " unique, stable key on the item, such as key=item or key=item.id."
            " See https://reflex.dev/docs/library/dynamic-rendering/foreach/",
            extra={"dedupe": True},
        )
