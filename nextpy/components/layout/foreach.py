"""Create a list of components from an iterable."""
from __future__ import annotations

import typing
from typing import Any, Callable, Iterable

from nextpy.components.component import Component
from nextpy.components.layout.fragment import Fragment
from nextpy.components.tags import IterTag
from nextpy.core.vars import BaseVar, Var, get_unique_variable_name


class Foreach(Component):
    """A component that takes in an iterable and a render function and renders a list of components."""

    # The iterable to create components from.
    iterable: Var[Iterable]

    # A function from the render args to the component.
    render_fn: Callable = Fragment.create

    @classmethod
    def create(cls, iterable: Var[Iterable], render_fn: Callable, **props) -> Foreach:
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
            type_ = (
                iterable._var_type
                if iterable._var_type.mro()[0] == dict
                else iterable._var_type.__args__[0]
            )
        except Exception:
            type_ = Any
        iterable = Var.create(iterable)  # type: ignore
        if iterable._var_type == Any:
            raise TypeError(
                f"Could not foreach over var of type Any. (If you are trying to foreach over a state var, add a type annotation to the var.)"
            )
        arg = BaseVar(_var_name="_", _var_type=type_, _var_is_local=True)
        comp = IterTag(iterable=iterable, render_fn=render_fn).render_component(arg)
        return cls(
            iterable=iterable,
            render_fn=render_fn,
            children=[comp],
            **props,
        )

    def _render(self) -> IterTag:
        return IterTag(
            iterable=self.iterable,
            render_fn=self.render_fn,
            index_var_name=get_unique_variable_name(),
        )

    def render(self):
        """Render the component.

        Returns:
            The dictionary for template of component.
        """
        tag = self._render()
        try:
            type_ = (
                tag.iterable._var_type
                if tag.iterable._var_type.mro()[0] == dict
                else typing.get_args(tag.iterable._var_type)[0]
            )
        except Exception:
            type_ = Any
        arg = BaseVar(
            _var_name=get_unique_variable_name(),
            _var_type=type_,
        )
        index_arg = tag.get_index_var_arg()
        component = tag.render_component(arg)
        return dict(
            tag.add_props(
                **self.event_triggers,
                key=self.key,
                sx=self.style,
                id=self.id,
                class_name=self.class_name,
            ).set(
                children=[component.render()],
                props=tag.format_props(),
            ),
            iterable_state=tag.iterable._var_full_name,
            arg_name=arg._var_name,
            arg_index=index_arg,
            iterable_type=tag.iterable._var_type.mro()[0].__name__,
        )
