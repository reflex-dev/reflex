"""Tag to loop through a list of components."""
from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Callable, List

from pynecone import utils
from pynecone.components.tags.tag import Tag
from pynecone.var import BaseVar, Var

if TYPE_CHECKING:
    from pynecone.components.component import Component


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
        index = Var.create(INDEX_VAR, is_local=False)
        assert index is not None
        return index

    @staticmethod
    def get_index_var_arg() -> Var:
        """Get the index var for the tag.

        Returns:
            The index var.
        """
        arg = Var.create(INDEX_VAR)
        assert arg is not None
        return arg

    @staticmethod
    def render_component(render_fn: Callable, arg: Var) -> Component:
        """Render the component.

        Args:
            render_fn: The render function.
            arg: The argument to pass to the render function.

        Returns:
            The rendered component.
        """
        args = inspect.getfullargspec(render_fn).args
        index = IterTag.get_index_var()
        if len(args) == 1:
            component = render_fn(arg)
        else:
            assert len(args) == 2
            component = render_fn(arg, index)
        if component.key is None:
            component.key = index
            # component.key = utils.wrap(str(index), "{", check_first=False)
        return component

    def __str__(self) -> str:
        """Render the tag as a React string.

        Returns:
            The React code to render the tag.
        """
        try:
            type_ = self.iterable.type_.__args__[0]
        except:
            type_ = Any
        arg = BaseVar(
            name=utils.get_unique_variable_name(),
            type_=type_,
        )
        index_arg = self.get_index_var_arg()
        component = self.render_component(self.render_fn, arg)
        return utils.wrap(
            f"{self.iterable.full_name}.map(({arg.name}, {index_arg}) => {component})",
            "{",
        )
