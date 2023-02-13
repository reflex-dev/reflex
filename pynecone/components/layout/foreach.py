"""Create a list of components from an iterable."""
from __future__ import annotations

from typing import Any, Callable, List

from pynecone.components.component import Component
from pynecone.components.tags import IterTag, Tag
from pynecone.var import BaseVar, Var


class Foreach(Component):
    """A component that takes in an iterable and a render function and renders a list of components."""

    # The iterable to create components from.
    iterable: Var[List]

    # A function from the render args to the component.
    render_fn: Callable

    @classmethod
    def create(cls, iterable: Var[List], render_fn: Callable, **props) -> Foreach:
        """Create a foreach component.

        Args:
            iterable: The iterable to create components from.
            render_fn: A function from the render args to the component.
            **props: The attributes to pass to each child component.

        Returns:
            The foreach component.

        Raises:
            TypeError: If the iterable is of type Any.
        """
        try:
            type_ = iterable.type_.__args__[0]
        except Exception:
            type_ = Any
        if iterable.type_ == Any:
            raise TypeError(
                f"Could not foreach over var of type Any. (If you are trying to foreach over a state var, add a type annotation to the var.)"
            )
        arg = BaseVar(name="_", type_=type_, is_local=True)
        return cls(
            iterable=iterable,
            render_fn=render_fn,
            children=[IterTag.render_component(render_fn, arg=arg)],
            **props,
        )

    def _render(self) -> Tag:
        return IterTag(iterable=self.iterable, render_fn=self.render_fn)
